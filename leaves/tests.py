from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from .holiday_data import INDIA_GAZETTED_HOLIDAYS_2026
from .models import Department, Employee, Holiday, LeaveBalance, LeaveRequest, LeaveType
from .services import (
    approve_leave_request,
    cancel_leave_request,
    count_working_days,
    reject_leave_request,
    validate_leave_request,
)


class WorkingDayTests(TestCase):
    def test_count_working_days_excludes_weekends_and_holidays(self):
        Holiday.objects.create(name='Republic Day', date=date(2026, 1, 26))
        self.assertEqual(count_working_days(date(2026, 1, 23), date(2026, 1, 28)), 3)

    def test_seed_public_holidays_command_loads_2026_dataset(self):
        call_command('seed_public_holidays', year=2026)

        self.assertEqual(Holiday.objects.count(), len(INDIA_GAZETTED_HOLIDAYS_2026))
        self.assertTrue(Holiday.objects.filter(name='Republic Day', date=date(2026, 1, 26)).exists())
        self.assertTrue(Holiday.objects.filter(name='Christmas Day', date=date(2026, 12, 25)).exists())


class LeaveWorkflowTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name='Engineering')
        self.manager_user = User.objects.create_user(username='manager', password='pass12345')
        self.employee_user = User.objects.create_user(username='employee', password='pass12345')
        self.superuser_user = User.objects.create_superuser(username='superadmin', password='pass12345', email='admin@example.com')
        self.manager = Employee.objects.create(
            user=self.manager_user,
            department=self.department,
            designation='Engineering Manager',
            date_of_joining=date(2020, 1, 1),
            is_manager=True,
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department=self.department,
            designation='Software Engineer',
            date_of_joining=date(2024, 1, 1),
            is_manager=False,
        )
        self.superuser_employee = Employee.objects.create(
            user=self.superuser_user,
            department=self.other_department if hasattr(self, 'other_department') else None,
            designation='HR Administrator',
            date_of_joining=date(2019, 1, 1),
            is_manager=False,
        )
        self.department.head = self.manager
        self.department.save(update_fields=['head'])
        self.leave_type = LeaveType.objects.create(name='Casual', max_days_per_year=12, is_paid=True, carry_forward=False)
        self.balance = LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2026,
            allocated_days=12,
            used_days=0,
        )
        self.other_department = Department.objects.create(name='Finance')
        self.other_manager_user = User.objects.create_user(username='othermanager', password='pass12345')
        self.other_manager = Employee.objects.create(
            user=self.other_manager_user,
            department=self.other_department,
            designation='Finance Manager',
            date_of_joining=date(2021, 1, 1),
            is_manager=True,
        )
        LeaveBalance.objects.create(
            employee=self.superuser_employee,
            leave_type=self.leave_type,
            year=2026,
            allocated_days=12,
            used_days=0,
        )

    def test_manager_approval_deducts_balance(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 28),
            reason='Family event',
        )
        approve_leave_request(leave_request, self.manager, 'Approved')
        self.balance.refresh_from_db()
        leave_request.refresh_from_db()
        self.assertEqual(self.balance.used_days, 2)
        self.assertEqual(leave_request.status, LeaveRequest.Status.APPROVED)

    def test_cancel_approved_leave_restores_balance(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 28),
            reason='Family event',
            status=LeaveRequest.Status.APPROVED,
        )
        self.balance.used_days = 2
        self.balance.save(update_fields=['used_days'])
        cancel_leave_request(leave_request, self.employee)
        self.balance.refresh_from_db()
        leave_request.refresh_from_db()
        self.assertEqual(self.balance.used_days, 0)
        self.assertEqual(leave_request.status, LeaveRequest.Status.CANCELLED)

    def test_approval_fails_when_balance_missing(self):
        self.balance.delete()
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 28),
            reason='Family event',
        )
        with self.assertRaises(ValidationError):
            approve_leave_request(leave_request, self.manager, 'Approved')

    def test_validate_leave_request_rejects_overlap_with_approved_leave(self):
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 28),
            reason='Existing approved leave',
            status=LeaveRequest.Status.APPROVED,
        )

        with self.assertRaises(ValidationError):
            validate_leave_request(
                self.employee,
                self.leave_type,
                date(2026, 4, 28),
                date(2026, 4, 29),
            )

    def test_reject_leave_requires_rejection_reason(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 29),
            end_date=date(2026, 4, 30),
            reason='Personal work',
        )

        with self.assertRaises(ValidationError):
            reject_leave_request(leave_request, self.manager, '')

    def test_validate_leave_request_rejects_cross_year_dates(self):
        with self.assertRaises(ValidationError):
            validate_leave_request(
                self.employee,
                self.leave_type,
                date(2026, 12, 31),
                date(2027, 1, 2),
            )

    def test_manager_cannot_review_other_department_request(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 29),
            end_date=date(2026, 4, 30),
            reason='Travel',
        )

        with self.assertRaises(PermissionDenied):
            approve_leave_request(leave_request, self.other_manager, 'Approved')

    def test_superuser_can_approve_manager_leave(self):
        manager_balance = LeaveBalance.objects.create(
            employee=self.manager,
            leave_type=self.leave_type,
            year=2026,
            allocated_days=12,
            used_days=0,
        )
        leave_request = LeaveRequest.objects.create(
            employee=self.manager,
            leave_type=self.leave_type,
            start_date=date(2026, 5, 6),
            end_date=date(2026, 5, 7),
            reason='Leadership offsite',
        )

        approve_leave_request(leave_request, self.superuser_employee, 'Approved by admin')

        manager_balance.refresh_from_db()
        leave_request.refresh_from_db()
        self.assertEqual(manager_balance.used_days, 2)
        self.assertEqual(leave_request.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(leave_request.reviewed_by, self.superuser_employee)

    def test_superuser_cannot_approve_own_leave(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.superuser_employee,
            leave_type=self.leave_type,
            start_date=date(2026, 5, 11),
            end_date=date(2026, 5, 12),
            reason='Admin leave',
        )

        with self.assertRaises(PermissionDenied):
            approve_leave_request(leave_request, self.superuser_employee, 'Self approved')

    def test_cancel_approved_leave_fails_after_start_date(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 28),
            reason='Family event',
            status=LeaveRequest.Status.APPROVED,
        )
        self.balance.used_days = 2
        self.balance.save(update_fields=['used_days'])

        with patch('leaves.services.timezone.localdate', return_value=date(2026, 4, 27)):
            with self.assertRaises(ValidationError):
                cancel_leave_request(leave_request, self.employee)

    def test_new_request_email_notifies_department_managers(self):
        self.manager.user.email = 'manager@example.com'
        self.manager.user.save(update_fields=['email'])
        second_manager_user = User.objects.create_user(
            username='leadmanager',
            password='pass12345',
            email='leadmanager@example.com',
        )
        Employee.objects.create(
            user=second_manager_user,
            department=self.department,
            designation='Team Lead',
            date_of_joining=date(2022, 1, 1),
            is_manager=True,
        )

        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 5, 4),
            end_date=date(2026, 5, 5),
            reason='Medical appointment',
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(
            mail.outbox[0].to,
            ['manager@example.com', 'leadmanager@example.com'],
        )

    def test_employee_can_submit_leave_from_web_form(self):
        self.client.login(username='employee', password='pass12345')
        response = self.client.post(
            reverse('apply_leave'),
            {
                'leave_type': self.leave_type.pk,
                'start_date': '2026-04-27',
                'end_date': '2026-04-28',
                'reason': 'Medical appointment',
            },
        )
        self.assertEqual(response.status_code, 302)
        created_request = LeaveRequest.objects.get(reason='Medical appointment')
        self.assertEqual(created_request.employee, self.employee)
        self.assertEqual(created_request.status, LeaveRequest.Status.PENDING)


class LeaveApiTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name='Engineering')
        self.other_department = Department.objects.create(name='HR')

        self.manager_user = User.objects.create_user(username='manager', password='pass12345')
        self.employee_user = User.objects.create_user(username='employee', password='pass12345')
        self.other_manager_user = User.objects.create_user(username='othermanager', password='pass12345')
        self.superuser_user = User.objects.create_superuser(username='superadmin', password='pass12345', email='admin@example.com')

        self.manager = Employee.objects.create(
            user=self.manager_user,
            department=self.department,
            designation='Engineering Manager',
            date_of_joining=date(2020, 1, 1),
            is_manager=True,
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department=self.department,
            designation='Software Engineer',
            date_of_joining=date(2024, 1, 1),
            is_manager=False,
        )
        self.other_manager = Employee.objects.create(
            user=self.other_manager_user,
            department=self.other_department,
            designation='HR Manager',
            date_of_joining=date(2021, 1, 1),
            is_manager=True,
        )
        self.superuser_employee = Employee.objects.create(
            user=self.superuser_user,
            department=self.other_department,
            designation='System Administrator',
            date_of_joining=date(2019, 1, 1),
            is_manager=False,
        )

        self.leave_type = LeaveType.objects.create(name='Casual', max_days_per_year=12, is_paid=True, carry_forward=False)
        self.balance = LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2026,
            allocated_days=12,
            used_days=0,
        )

    def test_manager_pending_api_lists_same_department_requests(self):
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 28),
            reason='Medical appointment',
        )

        self.client.login(username='manager', password='pass12345')
        response = self.client.get(reverse('api_manager_pending'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_manager_reject_api_requires_reason(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 28),
            reason='Medical appointment',
        )

        self.client.login(username='manager', password='pass12345')
        response = self.client.post(reverse('api_manager_reject', args=[leave_request.pk]), {})

        self.assertEqual(response.status_code, 400)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, LeaveRequest.Status.PENDING)

    def test_manager_approve_api_blocks_other_department_manager(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 4, 27),
            end_date=date(2026, 4, 28),
            reason='Medical appointment',
        )

        self.client.login(username='othermanager', password='pass12345')
        response = self.client.post(reverse('api_manager_approve', args=[leave_request.pk]), {})

        self.assertEqual(response.status_code, 403)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, LeaveRequest.Status.PENDING)

    def test_manager_pending_api_rejects_non_manager(self):
        self.client.login(username='employee', password='pass12345')
        response = self.client.get(reverse('api_manager_pending'))

        self.assertEqual(response.status_code, 403)

    def test_superuser_pending_api_lists_manager_requests(self):
        LeaveBalance.objects.create(
            employee=self.manager,
            leave_type=self.leave_type,
            year=2026,
            allocated_days=12,
            used_days=0,
        )
        LeaveRequest.objects.create(
            employee=self.manager,
            leave_type=self.leave_type,
            start_date=date(2026, 5, 15),
            end_date=date(2026, 5, 16),
            reason='Manager leave',
        )

        self.client.login(username='superadmin', password='pass12345')
        response = self.client.get(reverse('api_manager_pending'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)


class HolidayReminderDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='employee', password='pass12345')
        self.department = Department.objects.create(name='People Operations')
        self.employee = Employee.objects.create(
            user=self.user,
            department=self.department,
            designation='Operations Associate',
            date_of_joining=date(2024, 1, 1),
            is_manager=False,
        )
        self.leave_type = LeaveType.objects.create(name='Casual', max_days_per_year=12, is_paid=True, carry_forward=False)
        LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2026,
            allocated_days=12,
            used_days=0,
        )

    def test_dashboard_shows_tomorrow_holiday_reminder(self):
        Holiday.objects.create(name='Republic Day', date=date(2026, 1, 26))
        self.client.login(username='employee', password='pass12345')

        with patch('leaves.views.timezone.localdate', return_value=date(2026, 1, 25)):
            response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Reminder: tomorrow is a public holiday')
        self.assertContains(response, 'Republic Day is coming tomorrow')

    def test_dashboard_shows_today_holiday_message(self):
        Holiday.objects.create(name='Republic Day', date=date(2026, 1, 26))
        self.client.login(username='employee', password='pass12345')

        with patch('leaves.views.timezone.localdate', return_value=date(2026, 1, 26)):
            response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Today is a public holiday')
        self.assertContains(response, 'Leave requests are not needed for today')

    def test_dashboard_counts_only_paid_leave_in_summary(self):
        unpaid = LeaveType.objects.create(name='Unpaid', max_days_per_year=365, is_paid=False, carry_forward=False)
        sick = LeaveType.objects.create(name='Sick', max_days_per_year=10, is_paid=True, carry_forward=False)
        earned = LeaveType.objects.create(name='Earned', max_days_per_year=18, is_paid=True, carry_forward=False)
        LeaveBalance.objects.create(employee=self.employee, leave_type=unpaid, year=2026, allocated_days=365, used_days=0)
        LeaveBalance.objects.create(employee=self.employee, leave_type=sick, year=2026, allocated_days=10, used_days=0)
        LeaveBalance.objects.create(employee=self.employee, leave_type=earned, year=2026, allocated_days=18, used_days=0)

        self.client.login(username='employee', password='pass12345')
        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Paid Leave Remaining')
        self.assertContains(response, '<strong>40</strong>', html=True)


class TeamCalendarViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name='People Operations')
        self.user = User.objects.create_user(username='employee', password='pass12345')
        self.teammate_user = User.objects.create_user(username='teammate', password='pass12345')
        self.employee = Employee.objects.create(
            user=self.user,
            department=self.department,
            designation='Operations Associate',
            date_of_joining=date(2024, 1, 1),
            is_manager=False,
        )
        self.teammate = Employee.objects.create(
            user=self.teammate_user,
            department=self.department,
            designation='HR Specialist',
            date_of_joining=date(2024, 1, 1),
            is_manager=False,
        )
        self.leave_type = LeaveType.objects.create(name='Casual', max_days_per_year=12, is_paid=True, carry_forward=False)
        LeaveBalance.objects.create(employee=self.employee, leave_type=self.leave_type, year=2026, allocated_days=12, used_days=0)
        LeaveBalance.objects.create(employee=self.teammate, leave_type=self.leave_type, year=2026, allocated_days=12, used_days=0)

    def test_team_calendar_view_shows_approved_leave_on_month_grid(self):
        Holiday.objects.create(name='Republic Day', date=date(2026, 6, 15))
        LeaveRequest.objects.create(
            employee=self.teammate,
            leave_type=self.leave_type,
            start_date=date(2026, 6, 15),
            end_date=date(2026, 6, 16),
            reason='Planned leave',
            status=LeaveRequest.Status.APPROVED,
        )
        self.client.login(username='employee', password='pass12345')

        response = self.client.get(reverse('team_calendar') + '?year=2026&month=6')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'June 2026')
        self.assertContains(response, 'teammate')
        self.assertContains(response, 'Casual')
        self.assertContains(response, 'Republic Day')
        self.assertContains(response, 'Sunday')
