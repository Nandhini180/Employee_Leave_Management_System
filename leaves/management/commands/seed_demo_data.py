from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from leaves.holiday_data import INDIA_GAZETTED_HOLIDAYS_2026
from leaves.models import Department, Employee, Holiday, LeaveBalance, LeaveRequest, LeaveType


class Command(BaseCommand):
    help = 'Create a complete demo setup with manager, employees, leave types, balances, and sample leave requests.'

    def handle(self, *args, **options):
        password = 'Demo@12345'

        department, _ = Department.objects.get_or_create(name='People Operations')

        users_config = [
            {
                'username': 'admin@leavehub.local',
                'email': 'admin@leavehub.local',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True,
                'designation': 'System Administrator',
                'date_of_joining': date(2023, 1, 1),
                'is_manager': True,
                'department': 'Administration',
                'password': 'Admin@12345',
            },
            {
                'username': 'nandhini.v.2367@gmail.com',
                'email': 'nandhini.v.2367@gmail.com',
                'first_name': 'Nandhini',
                'last_name': 'Manager',
                'is_staff': True,
                'is_superuser': False,
                'designation': 'People Operations Manager',
                'date_of_joining': date(2023, 6, 1),
                'is_manager': True,
                'department': 'People Operations',
                'password': password,
            },
            {
                'username': 'poorni@gmail.com',
                'email': 'poorni@gmail.com',
                'first_name': 'Poorni',
                'last_name': 'Employee',
                'is_staff': False,
                'is_superuser': False,
                'designation': 'Operations Associate',
                'date_of_joining': date(2024, 7, 15),
                'is_manager': False,
                'department': 'People Operations',
                'password': password,
            },
            {
                'username': 'meera@gmail.com',
                'email': 'meera@gmail.com',
                'first_name': 'Meera',
                'last_name': 'Krishnan',
                'is_staff': False,
                'is_superuser': False,
                'designation': 'HR Specialist',
                'date_of_joining': date(2024, 2, 12),
                'is_manager': False,
                'department': 'People Operations',
                'password': password,
            },
            {
                'username': 'arjun@gmail.com',
                'email': 'arjun@gmail.com',
                'first_name': 'Arjun',
                'last_name': 'Prakash',
                'is_staff': False,
                'is_superuser': False,
                'designation': 'Talent Coordinator',
                'date_of_joining': date(2025, 1, 5),
                'is_manager': False,
                'department': 'People Operations',
                'password': password,
            },
            {
                'username': 'kaviya@gmail.com',
                'email': 'kaviya@gmail.com',
                'first_name': 'Kaviya',
                'last_name': 'Raman',
                'is_staff': False,
                'is_superuser': False,
                'designation': 'HR Analyst',
                'date_of_joining': date(2025, 3, 20),
                'is_manager': False,
                'department': 'People Operations',
                'password': password,
            },
        ]

        employees = {}
        for config in users_config:
            department_obj, _ = Department.objects.get_or_create(name=config['department'])
            user, _ = User.objects.get_or_create(
                username=config['username'],
                defaults={
                    'email': config['email'],
                    'first_name': config['first_name'],
                    'last_name': config['last_name'],
                    'is_staff': config['is_staff'],
                },
            )
            user.email = config['email']
            user.first_name = config['first_name']
            user.last_name = config['last_name']
            user.is_active = True
            user.is_staff = config['is_staff']
            user.is_superuser = config['is_superuser']
            user.set_password(config['password'])
            user.save()

            employee, _ = Employee.objects.update_or_create(
                user=user,
                defaults={
                    'department': department_obj,
                    'designation': config['designation'],
                    'date_of_joining': config['date_of_joining'],
                    'is_manager': config['is_manager'],
                },
            )
            employees[config['username']] = employee

        manager = employees['nandhini.v.2367@gmail.com']
        department.head = manager
        department.save(update_fields=['head'])
        admin_department = Department.objects.get(name='Administration')
        admin_department.head = employees['admin@leavehub.local']
        admin_department.save(update_fields=['head'])

        for holiday_name, holiday_date in INDIA_GAZETTED_HOLIDAYS_2026:
            Holiday.objects.update_or_create(
                date=holiday_date,
                defaults={'name': holiday_name},
            )

        leave_type_specs = [
            ('Casual', 10, True, False),
            ('Sick', 10, True, False),
            ('Earned', 10, True, True),
            ('Unpaid', 10, False, False),
        ]
        leave_types = {}
        for name, max_days, is_paid, carry_forward in leave_type_specs:
            leave_types[name], _ = LeaveType.objects.update_or_create(
                name=name,
                defaults={
                    'max_days_per_year': max_days,
                    'is_paid': is_paid,
                    'carry_forward': carry_forward,
                },
            )

        used_days_map = {
            ('admin@leavehub.local', 'Casual'): 1,
            ('nandhini.v.2367@gmail.com', 'Earned'): 3,
            ('poorni@gmail.com', 'Casual'): 2,
            ('meera@gmail.com', 'Casual'): 3,
            ('arjun@gmail.com', 'Sick'): 1,
            ('kaviya@gmail.com', 'Earned'): 4,
        }

        for username, user_employee in employees.items():
            for name, leave_type in leave_types.items():
                LeaveBalance.objects.update_or_create(
                    employee=user_employee,
                    leave_type=leave_type,
                    year=2026,
                    defaults={
                        'allocated_days': leave_type.max_days_per_year,
                        'used_days': used_days_map.get((username, name), 0),
                    },
                )

        request_specs = [
            {
                'employee': employees['poorni@gmail.com'],
                'leave_type': leave_types['Casual'],
                'start_date': date(2026, 5, 4),
                'end_date': date(2026, 5, 5),
                'reason': 'Family function and travel.',
                'status': LeaveRequest.Status.APPROVED,
                'reviewed_by': manager,
                'manager_note': 'Approved for planned travel.',
                'rejection_reason': '',
            },
            {
                'employee': employees['poorni@gmail.com'],
                'leave_type': leave_types['Sick'],
                'start_date': date(2026, 5, 18),
                'end_date': date(2026, 5, 19),
                'reason': 'Medical consultation and recovery.',
                'status': LeaveRequest.Status.PENDING,
                'reviewed_by': None,
                'manager_note': '',
                'rejection_reason': '',
            },
            {
                'employee': employees['meera@gmail.com'],
                'leave_type': leave_types['Earned'],
                'start_date': date(2026, 5, 25),
                'end_date': date(2026, 5, 27),
                'reason': 'Attending sibling wedding out of town.',
                'status': LeaveRequest.Status.PENDING,
                'reviewed_by': None,
                'manager_note': '',
                'rejection_reason': '',
            },
            {
                'employee': employees['arjun@gmail.com'],
                'leave_type': leave_types['Casual'],
                'start_date': date(2026, 6, 2),
                'end_date': date(2026, 6, 3),
                'reason': 'Short personal break.',
                'status': LeaveRequest.Status.APPROVED,
                'reviewed_by': manager,
                'manager_note': 'Coverage confirmed.',
                'rejection_reason': '',
            },
            {
                'employee': employees['kaviya@gmail.com'],
                'leave_type': leave_types['Sick'],
                'start_date': date(2026, 6, 11),
                'end_date': date(2026, 6, 12),
                'reason': 'Recovery after viral fever.',
                'status': LeaveRequest.Status.APPROVED,
                'reviewed_by': manager,
                'manager_note': 'Please take care.',
                'rejection_reason': '',
            },
            {
                'employee': employees['kaviya@gmail.com'],
                'leave_type': leave_types['Casual'],
                'start_date': date(2026, 7, 8),
                'end_date': date(2026, 7, 10),
                'reason': 'Family event arrangements.',
                'status': LeaveRequest.Status.REJECTED,
                'reviewed_by': manager,
                'manager_note': 'Project interview drive is scheduled that week.',
                'rejection_reason': 'Department coverage is not available for those dates.',
            },
            {
                'employee': manager,
                'leave_type': leave_types['Earned'],
                'start_date': date(2026, 6, 8),
                'end_date': date(2026, 6, 10),
                'reason': 'Personal vacation.',
                'status': LeaveRequest.Status.APPROVED,
                'reviewed_by': None,
                'manager_note': '',
                'rejection_reason': '',
            },
            {
                'employee': employees['admin@leavehub.local'],
                'leave_type': leave_types['Casual'],
                'start_date': date(2026, 6, 16),
                'end_date': date(2026, 6, 16),
                'reason': 'System maintenance planning day.',
                'status': LeaveRequest.Status.APPROVED,
                'reviewed_by': None,
                'manager_note': '',
                'rejection_reason': '',
            },
        ]

        for spec in request_specs:
            LeaveRequest.objects.update_or_create(
                employee=spec['employee'],
                leave_type=spec['leave_type'],
                start_date=spec['start_date'],
                end_date=spec['end_date'],
                defaults={
                    'reason': spec['reason'],
                    'status': spec['status'],
                    'reviewed_by': spec['reviewed_by'],
                    'manager_note': spec['manager_note'],
                    'rejection_reason': spec['rejection_reason'],
                },
            )

        self.stdout.write(self.style.SUCCESS('Demo setup completed successfully.'))
        self.stdout.write('Admin login: admin@leavehub.local / Admin@12345')
        self.stdout.write('Manager login: nandhini.v.2367@gmail.com / Demo@12345')
        self.stdout.write('Employee login: poorni@gmail.com / Demo@12345')
        self.stdout.write('Additional demo users: meera@gmail.com, arjun@gmail.com, kaviya@gmail.com / Demo@12345')
