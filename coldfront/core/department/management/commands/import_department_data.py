import os

from django.core.management.base import BaseCommand, CommandError

from coldfront.core.department.models import Department

app_commands_dir = os.path.dirname(__file__)

class Command(BaseCommand):
    help = 'Import department data'

    def handle(self, *args, **options):
        print('Adding departments ...')
        file_path = os.path.join(app_commands_dir, 'data', 'department_data.csv')
        with open(file_path, 'r') as fp:
            for line in fp:
                catalog_code, name, academic_group, academic_organization = line.strip().split(',')

                fos = Department.objects.get_or_create(
                    catalog_code=catalog_code,
                    name=name,
                    academic_group=academic_group,
                    academic_organization=academic_organization
                )                

        print('Finished adding departments')
