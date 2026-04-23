from django.core.management.base import BaseCommand, CommandError

from leaves.holiday_data import INDIA_GAZETTED_HOLIDAYS_2026
from leaves.models import Holiday


class Command(BaseCommand):
    help = 'Seed public holidays for a given year.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, required=True, help='Year to seed holidays for.')

    def handle(self, *args, **options):
        year = options['year']
        if year != 2026:
            raise CommandError('This project currently ships with a curated holiday dataset for 2026 only.')

        created_count = 0
        updated_count = 0

        for name, holiday_date in INDIA_GAZETTED_HOLIDAYS_2026:
            holiday, created = Holiday.objects.update_or_create(
                date=holiday_date,
                defaults={'name': name},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Year {year}: created {created_count} holiday(s), updated {updated_count} holiday(s).'
            )
        )
