import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import get_employee_profile, require_employee_profile
from .forms import LeaveApplicationForm, ManagerDecisionForm
from .models import Holiday, LeaveRequest
from .serializers import (
    LeaveBalanceSerializer,
    LeaveRequestActionSerializer,
    LeaveRequestCreateSerializer,
    LeaveRequestSerializer,
)
from .services import approve_leave_request, cancel_leave_request, reject_leave_request


def _raise_api_exception(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        messages = exc.messages if hasattr(exc, 'messages') else [str(exc)]
        raise ValidationError(messages) from exc
    raise exc


def _build_holiday_alerts(today):
    alerts = []
    today_holiday = Holiday.objects.filter(date=today).first()
    tomorrow = today + timedelta(days=1)
    tomorrow_holiday = Holiday.objects.filter(date=tomorrow).first()

    if today_holiday:
        alerts.append(
            {
                'level': 'holiday-today',
                'title': 'Today is a public holiday',
                'message': f'{today_holiday.name} is a company holiday today. Leave requests are not needed for today.',
            }
        )
    if tomorrow_holiday:
        alerts.append(
            {
                'level': 'holiday-upcoming',
                'title': 'Reminder: tomorrow is a public holiday',
                'message': f'{tomorrow_holiday.name} is coming tomorrow. Please plan team work and leave schedules accordingly.',
            }
        )
    return alerts


def _get_scope_approved_requests(employee, user, today):
    base_queryset = LeaveRequest.objects.select_related('employee__user', 'leave_type').filter(
        status=LeaveRequest.Status.APPROVED,
        end_date__gte=today,
    )
    if user.is_superuser:
        return base_queryset
    if employee.department_id:
        return base_queryset.filter(employee__department=employee.department)
    return base_queryset.none()


def _build_calendar_weeks(requests, year, month):
    request_map = defaultdict(list)
    month_start = date(year, month, 1)
    _, month_days = calendar.monthrange(year, month)
    month_end = date(year, month, month_days)
    holiday_map = {
        holiday.date: holiday
        for holiday in Holiday.objects.filter(date__range=(month_start, month_end))
    }

    for item in requests:
        current = max(item.start_date, month_start)
        end = min(item.end_date, month_end)
        while current <= end:
            request_map[current].append(item)
            current += timedelta(days=1)

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        week_cells = []
        for day in week:
            week_cells.append(
                {
                    'date': day,
                    'in_month': day.month == month,
                    'is_today': day == timezone.localdate(),
                    'is_weekend': day.weekday() >= 5,
                    'weekend_label': 'Saturday' if day.weekday() == 5 else 'Sunday' if day.weekday() == 6 else '',
                    'holiday': holiday_map.get(day),
                    'items': request_map.get(day, []),
                }
            )
        weeks.append(week_cells)
    return weeks


class LeaveRequestListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        employee = require_employee_profile(self.request.user)
        return LeaveRequest.objects.select_related('employee__user', 'leave_type', 'reviewed_by__user').filter(
            employee=employee
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LeaveRequestCreateSerializer
        return LeaveRequestSerializer


class LeaveCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        employee = require_employee_profile(request.user)
        leave_request = get_object_or_404(LeaveRequest, pk=pk, employee=employee)
        try:
            cancel_leave_request(leave_request, employee)
        except Exception as exc:
            _raise_api_exception(exc)
        return Response({'detail': 'Leave request cancelled successfully.'}, status=status.HTTP_200_OK)


class ManagerPendingLeaveAPIView(generics.ListAPIView):
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        employee = require_employee_profile(self.request.user)
        if self.request.user.is_superuser:
            return LeaveRequest.objects.select_related('employee__user', 'leave_type').filter(
                status=LeaveRequest.Status.PENDING,
            ).exclude(employee=employee)
        if not employee.is_manager:
            raise PermissionDenied('Only managers or superusers can view pending leave requests.')
        if not employee.department_id:
            raise PermissionDenied('Managers must belong to a department to view pending leave requests.')
        return LeaveRequest.objects.select_related('employee__user', 'leave_type').filter(
            employee__department=employee.department,
            status=LeaveRequest.Status.PENDING,
        ).exclude(employee=employee)


class ManagerApproveLeaveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        serializer = LeaveRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave_request = get_object_or_404(LeaveRequest, pk=pk)
        try:
            approve_leave_request(
                leave_request,
                require_employee_profile(request.user),
                serializer.validated_data.get('manager_note', ''),
            )
        except Exception as exc:
            _raise_api_exception(exc)
        return Response({'detail': 'Leave request approved successfully.'}, status=status.HTTP_200_OK)


class ManagerRejectLeaveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        serializer = LeaveRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave_request = get_object_or_404(LeaveRequest, pk=pk)
        try:
            reject_leave_request(
                leave_request,
                require_employee_profile(request.user),
                serializer.validated_data.get('rejection_reason', ''),
                serializer.validated_data.get('manager_note', ''),
            )
        except Exception as exc:
            _raise_api_exception(exc)
        return Response({'detail': 'Leave request rejected successfully.'}, status=status.HTTP_200_OK)


class LeaveBalanceAPIView(generics.ListAPIView):
    serializer_class = LeaveBalanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return require_employee_profile(self.request.user).leave_balances.select_related('leave_type').all()


@login_required
def dashboard(request):
    employee = get_employee_profile(request.user)
    today = timezone.localdate()
    if employee is None:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('/admin/')
        return render(request, 'leaves/no_employee_profile.html', {'is_admin_user': request.user.is_staff or request.user.is_superuser})
    own_requests = employee.leave_requests.select_related('leave_type', 'reviewed_by__user').all()
    balances = employee.leave_balances.select_related('leave_type').all()
    pending_requests = []
    team_calendar = defaultdict(list)
    summary = {
        'available_days': sum(balance.remaining_days for balance in balances if balance.leave_type.is_paid),
        'pending_count': own_requests.filter(status=LeaveRequest.Status.PENDING).count(),
        'approved_count': own_requests.filter(status=LeaveRequest.Status.APPROVED).count(),
        'team_pending_count': 0,
    }

    approved_requests = _get_scope_approved_requests(employee, request.user, today)

    if request.user.is_superuser:
        pending_requests = LeaveRequest.objects.select_related('employee__user', 'leave_type').filter(
            status=LeaveRequest.Status.PENDING,
        ).exclude(employee=employee)
        summary['team_pending_count'] = pending_requests.count()
    elif employee.department_id:
        pending_requests = LeaveRequest.objects.select_related('employee__user', 'leave_type').filter(
            employee__department=employee.department,
            status=LeaveRequest.Status.PENDING,
        ).exclude(employee=employee)
        if employee.is_manager:
            summary['team_pending_count'] = pending_requests.count()

    for item in approved_requests:
        team_calendar[item.start_date.strftime('%b %d')].append(item)

    return render(
        request,
        'leaves/dashboard.html',
        {
            'employee': employee,
            'balances': balances,
            'own_requests': own_requests,
            'pending_requests': pending_requests,
            'team_calendar': dict(team_calendar),
            'summary': summary,
            'holiday_alerts': _build_holiday_alerts(today),
            'leave_form': LeaveApplicationForm(employee=employee),
            'manager_form': ManagerDecisionForm(),
            'today': today,
        },
    )


@login_required
def team_calendar_view(request):
    employee = get_employee_profile(request.user)
    if employee is None:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('/admin/')
        return render(request, 'leaves/no_employee_profile.html', {'is_admin_user': request.user.is_staff or request.user.is_superuser})

    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        current_month = date(year, month, 1)
    except ValueError:
        current_month = date(today.year, today.month, 1)

    prev_month = (current_month.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    approved_requests = _get_scope_approved_requests(employee, request.user, today)
    month_requests = approved_requests.filter(
        start_date__lte=date(current_month.year, current_month.month, calendar.monthrange(current_month.year, current_month.month)[1]),
        end_date__gte=current_month,
    )

    return render(
        request,
        'leaves/team_calendar.html',
        {
            'employee': employee,
            'today': today,
            'calendar_month': current_month,
            'calendar_weeks': _build_calendar_weeks(month_requests, current_month.year, current_month.month),
            'prev_month': prev_month,
            'next_month': next_month,
            'month_requests': month_requests,
            'holiday_alerts': _build_holiday_alerts(today),
        },
    )


@login_required
@require_http_methods(['POST'])
def apply_leave(request):
    employee = get_employee_profile(request.user)
    if employee is None:
        messages.error(request, 'Your user account is missing an employee profile. Please create one in the admin panel first.')
        return redirect('dashboard')
    form = LeaveApplicationForm(request.POST, employee=employee)
    if form.is_valid():
        form.save()
        messages.success(request, 'Leave request submitted successfully.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect('dashboard')


@login_required
@require_http_methods(['POST'])
def cancel_leave_web(request, pk):
    employee = get_employee_profile(request.user)
    if employee is None:
        messages.error(request, 'Your user account is missing an employee profile.')
        return redirect('dashboard')
    leave_request = get_object_or_404(LeaveRequest, pk=pk, employee=employee)
    try:
        cancel_leave_request(leave_request, employee)
        messages.success(request, 'Leave request cancelled successfully.')
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect('dashboard')


@login_required
@require_http_methods(['POST'])
def approve_leave_web(request, pk):
    employee = get_employee_profile(request.user)
    if employee is None:
        messages.error(request, 'Your user account is missing an employee profile.')
        return redirect('dashboard')
    if not (employee.is_manager or request.user.is_superuser):
        return HttpResponseForbidden('Only managers or superusers can approve leave.')
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    form = ManagerDecisionForm(request.POST)
    if form.is_valid():
        try:
            approve_leave_request(leave_request, employee, form.cleaned_data.get('manager_note', ''))
            messages.success(request, 'Leave request approved.')
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect('dashboard')


@login_required
@require_http_methods(['POST'])
def reject_leave_web(request, pk):
    employee = get_employee_profile(request.user)
    if employee is None:
        messages.error(request, 'Your user account is missing an employee profile.')
        return redirect('dashboard')
    if not (employee.is_manager or request.user.is_superuser):
        return HttpResponseForbidden('Only managers or superusers can reject leave.')
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    form = ManagerDecisionForm(request.POST)
    if form.is_valid():
        try:
            reject_leave_request(
                leave_request,
                employee,
                form.cleaned_data.get('rejection_reason', ''),
                form.cleaned_data.get('manager_note', ''),
            )
            messages.success(request, 'Leave request rejected.')
        except Exception as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, 'Rejection reason is required.')
    return redirect('dashboard')
