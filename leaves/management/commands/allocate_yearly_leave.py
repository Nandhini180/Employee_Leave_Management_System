from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from leaves.models import Employee, LeaveBalance, LeaveType


class Command(BaseCommand):
    help = 'Allocate yearly leave balances for all employees.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, required=True, help='Year to allocate leave for.')

    def handle(self, *args, **options):
        year = options['year']
        created_count = 0

        for employee in Employee.objects.select_related('department').all():
            for leave_type in LeaveType.objects.all():
                allocated_days = leave_type.max_days_per_year
                if leave_type.carry_forward:
                    previous = LeaveBalance.objects.filter(
                        employee=employee,
                        leave_type=leave_type,
                        year=year - 1,
                    ).first()
                    if previous and previous.remaining_days > 0:
                        allocated_days += previous.remaining_days

                try:
                    with transaction.atomic():
                        _, created = LeaveBalance.objects.get_or_create(
                            employee=employee,
                            leave_type=leave_type,
                            year=year,
                            defaults={'allocated_days': allocated_days, 'used_days': 0},
                        )
                        if created:
                            created_count += 1
                except IntegrityError:
                    self.stderr.write(
                        self.style.WARNING(f'Balance already exists for {employee} / {leave_type} / {year}.')
                    )

        self.stdout.write(self.style.SUCCESS(f'Year {year}: created {created_count} leave balance record(s).'))
