from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Employee, Holiday, LeaveBalance, LeaveRequest


def count_working_days(start, end):
    days = 0
    current = start
    holiday_dates = set(Holiday.objects.filter(date__range=(start, end)).values_list('date', flat=True))
    while current <= end:
        if current.weekday() < 5 and current not in holiday_dates:
            days += 1
        current += timedelta(days=1)
    return days


def calculate_leave_days(start, end):
    return count_working_days(start, end)


def get_working_days_in_year(year):
    return count_working_days(date(year, 1, 1), date(year, 12, 31))


def get_balance_for_year(employee, leave_type, year):
    return LeaveBalance.objects.filter(employee=employee, leave_type=leave_type, year=year).first()


def validate_leave_request(employee, leave_type, start_date, end_date, exclude_request_id=None):
    if start_date > end_date:
        raise ValidationError('End date must be on or after start date.')
    if start_date.year != end_date.year:
        raise ValidationError('Leave requests cannot span multiple calendar years.')

    num_days = calculate_leave_days(start_date, end_date)
    if num_days <= 0:
        raise ValidationError('Selected dates do not include any working days.')

    balance = get_balance_for_year(employee, leave_type, start_date.year)
    if not balance:
        raise ValidationError('No leave balance allocated for the selected leave type and year.')
    if balance.remaining_days < num_days:
        raise ValidationError('Insufficient leave balance for this request.')

    overlap_query = LeaveRequest.objects.filter(
        Q(employee=employee, status=LeaveRequest.Status.APPROVED),
        Q(start_date__lte=end_date, end_date__gte=start_date),
    )
    if exclude_request_id:
        overlap_query = overlap_query.exclude(pk=exclude_request_id)
    if overlap_query.exists():
        raise ValidationError('You already have approved leave overlapping with the selected dates.')

    return num_days


def _assert_manager_can_review(leave_request, manager):
    if leave_request.employee_id == manager.id:
        raise PermissionDenied('Managers cannot review their own leave requests.')
    if manager.user.is_superuser:
        return
    if not manager.is_manager:
        raise PermissionDenied('Only managers or superusers can review leave requests.')
    if not manager.department_id or leave_request.employee.department_id != manager.department_id:
        raise PermissionDenied('Managers can review only requests from their own department.')


@transaction.atomic
def approve_leave_request(leave_request, manager, note=''):
    leave_request = LeaveRequest.objects.select_for_update().select_related('employee', 'leave_type').get(pk=leave_request.pk)
    _assert_manager_can_review(leave_request, manager)
    if leave_request.status != LeaveRequest.Status.PENDING:
        raise ValidationError('Only pending leave requests can be approved.')

    num_days = validate_leave_request(
        leave_request.employee,
        leave_request.leave_type,
        leave_request.start_date,
        leave_request.end_date,
        exclude_request_id=leave_request.pk,
    )
    balance = LeaveBalance.objects.select_for_update().get(
        employee=leave_request.employee,
        leave_type=leave_request.leave_type,
        year=leave_request.start_date.year,
    )

    balance.used_days += num_days
    balance.save(update_fields=['used_days'])

    leave_request.status = LeaveRequest.Status.APPROVED
    leave_request.reviewed_by = manager
    leave_request.reviewed_at = timezone.now()
    leave_request.manager_note = note
    leave_request.rejection_reason = ''
    leave_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'manager_note', 'rejection_reason', 'num_days'])
    return leave_request


@transaction.atomic
def reject_leave_request(leave_request, manager, rejection_reason, note=''):
    leave_request = LeaveRequest.objects.select_for_update().get(pk=leave_request.pk)
    _assert_manager_can_review(leave_request, manager)
    if leave_request.status != LeaveRequest.Status.PENDING:
        raise ValidationError('Only pending leave requests can be rejected.')
    if not rejection_reason:
        raise ValidationError('Rejection reason is required.')

    leave_request.status = LeaveRequest.Status.REJECTED
    leave_request.reviewed_by = manager
    leave_request.reviewed_at = timezone.now()
    leave_request.rejection_reason = rejection_reason
    leave_request.manager_note = note
    leave_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason', 'manager_note', 'num_days'])
    return leave_request


@transaction.atomic
def cancel_leave_request(leave_request, employee):
    leave_request = LeaveRequest.objects.select_for_update().select_related('leave_type').get(pk=leave_request.pk)
    if leave_request.employee_id != employee.id:
        raise PermissionDenied('You can cancel only your own leave requests.')

    today = timezone.localdate()
    if leave_request.status == LeaveRequest.Status.PENDING:
        leave_request.status = LeaveRequest.Status.CANCELLED
        leave_request.save(update_fields=['status', 'num_days'])
        return leave_request

    if leave_request.status == LeaveRequest.Status.APPROVED:
        if leave_request.start_date <= today:
            raise ValidationError('Approved leave cannot be cancelled once the start date has passed or started.')
        balance = LeaveBalance.objects.select_for_update().get(
            employee=employee,
            leave_type=leave_request.leave_type,
            year=leave_request.start_date.year,
        )
        balance.used_days = max(0, balance.used_days - leave_request.num_days)
        balance.save(update_fields=['used_days'])
        leave_request.status = LeaveRequest.Status.CANCELLED
        leave_request.save(update_fields=['status', 'num_days'])
        return leave_request

    raise ValidationError('Only pending or approved leave requests can be cancelled.')


def email_manager_on_new_request(leave_request):
    department = leave_request.employee.department
    if not department:
        return
    recipient_list = list(
        Employee.objects.filter(department=department, is_manager=True)
        .exclude(pk=leave_request.employee_id)
        .exclude(user__email='')
        .values_list('user__email', flat=True)
        .distinct()
    )
    if not recipient_list:
        return
    dashboard_url = f"{getattr(settings, 'APP_BASE_URL', 'http://localhost:8000').rstrip('/')}/"

    send_mail(
        subject='New leave request pending review',
        message=(
            f'A new leave request is pending your review.\n\n'
            f'Employee: {leave_request.employee}\n'
            f'Department: {department.name}\n'
            f'Leave type: {leave_request.leave_type.name}\n'
            f'Dates: {leave_request.start_date} to {leave_request.end_date}\n'
            f'Working days: {leave_request.num_days}\n'
            f'Reason: {leave_request.reason}\n\n'
            f'Open LeaveHub: {dashboard_url}'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=recipient_list,
        fail_silently=True,
    )
