from django.core.management.base import BaseCommand

from coldfront.core.allocation.models import (AttributeType,
                                              AllocationAttributeType,
                                              AllocationStatusChoice,
                                              AllocationChangeStatusChoice,
                                              AllocationUserStatusChoice,
                                              AllocationUserStorageStatusChoice,
                                              AllocationUserStoragePermissionChoice)


class Command(BaseCommand):
    help = 'Add default allocation related choices'

    def handle(self, *args, **options):

        for attribute_type in ('Date', 'Float', 'Int', 'Text', 'Yes/No', 'No',
            'Attribute Expanded Text'):
            AttributeType.objects.get_or_create(name=attribute_type)

        for choice in ('Active', 'Denied', 'Expired',
                       'New', 'Paid', 'Payment Pending',
                       'Payment Requested', 'Payment Declined',
                       'Renewal Requested', 'Revoked', 'Unpaid',):
            AllocationStatusChoice.objects.get_or_create(name=choice)

        for choice in ('Pending', 'Approved', 'Denied',):
            AllocationChangeStatusChoice.objects.get_or_create(name=choice)

        for choice in ('Active', 'Error', 'Removed', 'PendingEULA', 'DeclinedEULA', 'PendingStartDate', 'Deactivated'):
            AllocationUserStatusChoice.objects.get_or_create(name=choice)

        for choice in ('New', 'UpdateQuota', 'NewPermissions', 'ChangePermissions', 'Pending', 'Provisioned', 'None'):
            AllocationUserStorageStatusChoice.objects.get_or_create(name=choice)

        for choice in ('Read Only', 'Read and Write', 'None'):
            AllocationUserStoragePermissionChoice.objects.get_or_create(name=choice)

        for name, attribute_type, has_usage, is_private, is_changeable in (
            ('Cloud Account Name', 'Text', False, False, False),
            ('CLOUD_USAGE_NOTIFICATION', 'Yes/No', False, True, False),
            ('Core Usage (Hours)', 'Int', True, False, True),
            ('Accelerator Usage (Hours)', 'Int', True, False, True), 
            ('Memory Usage (Hours)', 'Int', True, False, True),           
            ('Cloud Storage Quota (TB)', 'Float', True, False, False),
            ('EXPIRE NOTIFICATION', 'Yes/No', False, True, False),
            ('freeipa_group', 'Text', False, False, False),
            ('Is Course?', 'Yes/No', False, True, False),
            ('Paid', 'Float', False, False, False),
            ('Paid Cloud Support (Hours)', 'Float', True, True, False),
            ('Paid Network Support (Hours)', 'Float', True, True, False),
            ('Paid Storage Support (Hours)', 'Float', True, True, False),
            ('Purchase Order Number', 'Int', False, True, False),
            ('send_expiry_email_on_date', 'Date', False, True, False),
            ('slurm_account_name', 'Text', False, False, False),
            ('slurm_specs', 'Attribute Expanded Text', False, True, False),
            ('slurm_specs_attriblist', 'Text', False, True, False),
            ('slurm_user_specs', 'Attribute Expanded Text', False, True, False),
            ('slurm_user_specs_attriblist', 'Text', False, True, False),
            ('Storage Quota (GB)', 'Int', True, False, True),
            ('Storage Quota (File Count)', 'Int', True, False, True),
            ('Storage Path', 'Text', False, False, False),
            ('Storage Project ID', 'Int', False, False, False),
            ('Storage_Group_Name', 'Text', False, False, False),
            ('Storage User Permissions', 'Text', False, False, True),
            ('Storage System', 'Text', False, False, False),
            ('Storage Path Stem', 'Text', False, False, False),
            ('SupportersQOS', 'Yes/No', False, False, False),
            ('SupportersQOSExpireDate', 'Date', False, False, False),
        ):
            AllocationAttributeType.objects.get_or_create(name=name, attribute_type=AttributeType.objects.get(
                name=attribute_type), has_usage=has_usage, is_private=is_private, is_changeable=is_changeable)
