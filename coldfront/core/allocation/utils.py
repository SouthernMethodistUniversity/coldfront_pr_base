# SPDX-FileCopyrightText: (C) ColdFront Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import PurePath
from django.db.models import Q
from django.contrib.auth import get_user_model
from coldfront.core.allocation.models import (Allocation,
                                              AllocationUser,
                                              AllocationUserStatusChoice,
                                              AllocationAttribute,
                                              AllocationAttributeType,
                                              AllocationPermission,
                                              AllocationUserStoragePermissionChoice,
                                              AllocationUserStorageStatusChoice)

from coldfront.core.resource.models import Resource


def set_allocation_user_status_to_error(allocation_user_pk):
    allocation_user_obj = AllocationUser.objects.get(pk=allocation_user_pk)
    error_status = AllocationUserStatusChoice.objects.get(name="Error")
    allocation_user_obj.status = error_status
    allocation_user_obj.save()


def generate_guauge_data_from_usage(name, value, usage):
    label = "%s: %.2f of %.2f" % (name, usage, value)

    try:
        percent = (usage / value) * 100
    except ZeroDivisionError:
        percent = 100
    except ValueError:
        percent = 100

    if percent < 80:
        color = "#6da04b"
    elif percent >= 80 and percent < 90:
        color = "#ffc72c"
    else:
        color = "#e56a54"

    usage_data = {
        "columns": [
            [label, percent],
        ],
        "type": "gauge",
        "colors": {label: color},
    }

    return usage_data


def get_user_resources(user_obj):
    if user_obj.is_superuser:
        resources = Resource.objects.filter(is_allocatable=True)
    else:
        resources = Resource.objects.filter(
            Q(is_allocatable=True)
            & Q(is_available=True)
            & (
                Q(is_public=True)
                | Q(allowed_groups__in=user_obj.groups.all())
                | Q(
                    allowed_users__in=[
                        user_obj,
                    ]
                )
            )
        ).distinct()

    return resources


def test_allocation_function(allocation_pk):
    print("test_allocation_function", allocation_pk)

def parse_allocation_attributes(allocation_obj, 
                                resource_obj,
                                project_obj, 
                                allocation_cpu_hours=0,
                                allocation_gpu_hours=0, 
                                allocation_memory_hours=0,
                                allocation_storage_capacity=0,
                                allocation_storage_file_count=0):
    
    n_project_allocations = allocation_obj.project.allocation_set.filter(
                    resources__resource_type__name='Cluster').count()
    n_storage_allocations = allocation_obj.project.allocation_set.filter(
                    resources__resource_type__name='Storage').count()
    if (resource_obj.resource_type.name == "Cluster"):
        value = project_obj.pi.username.lower() + '_' + project_obj.short_descriptor.replace(" ", "_").lower() + '_' + str(n_project_allocations).zfill(4)
        create_allocation_attributes(allocation_obj, 'slurm_account_name', value)
        
        # account limits
        slurm_specs = create_slurm_spec_string(allocation_cpu_hours, allocation_gpu_hours, allocation_memory_hours)
        if slurm_specs:
            create_allocation_attributes(allocation_obj, 'slurm_specs', slurm_specs)

            # user settings
            slurm_user_specs = create_slurm_user_spec_string()
            if slurm_user_specs:
                create_allocation_attributes(allocation_obj, 'slurm_user_specs', slurm_user_specs)

        #  set allocation attributes
        create_allocation_attributes(allocation_obj, 'Core Usage (Hours)', allocation_cpu_hours)
        create_allocation_attributes(allocation_obj, 'Accelerator Usage (Hours)', allocation_gpu_hours)
        create_allocation_attributes(allocation_obj, 'Memory Usage (Hours)', allocation_memory_hours)


    if (resource_obj.resource_type.name == "Storage"):
        value = '2' + str(project_obj.id).zfill(6) + str(n_storage_allocations).zfill(3)
        create_allocation_attributes(allocation_obj, 'Storage Project ID', value)
        stem = str(resource_obj.resourceattribute_set.filter(
            resource_attribute_type__name='Storage Path Stem').first().value)
        if not stem:
            stem = '/'

        allocation_folder = allocation_obj.folder_name
        if not allocation_folder:
            allocation_folder = 'allocation_' + str(n_storage_allocations).zfill(3)
        path_val = PurePath(stem).joinpath(project_obj.pi.username, 
                                           project_obj.short_descriptor,  
                                           allocation_folder)
        create_allocation_attributes(allocation_obj, 'Storage Path', str(path_val))
        create_allocation_attributes(allocation_obj, 'Storage Quota (GB)', allocation_storage_capacity)
        create_allocation_attributes(allocation_obj, 'Storage Quota (File Count)', allocation_storage_file_count)
        
def remove_user_from_allocation(allocation_obj, username, sender, requestor):

    # ensure requestor has permissions
    if not allocation_obj.has_perm(requestor, AllocationPermission.MANAGER) and not requestor.is_superuser:
        return False

    user_obj = get_user_model().objects.get(username=username)

    # PIs can't be removed form allocations
    if allocation_obj.project.pi == user_obj:
        return False
    
    allocation_user_removed_status_choice = AllocationUserStatusChoice.objects.get(
                name='Removed')
    permission_choice = AllocationUserStoragePermissionChoice.objects.get(name='None')
    permission_status = AllocationUserStorageStatusChoice.objects.get(name='ChangePermissions')

    try:
        allocation_user_obj = allocation_obj.allocationuser_set.get(user=user_obj)
        allocation_user_obj.status = allocation_user_removed_status_choice
        if (allocation_obj.get_parent_resource.resource_type.name == "Storage"):
            allocation_user_obj.storage_permissions = permission_choice
            allocation_user_obj.storage_status = permission_status
        allocation_user_obj.save()
    except Exception as e:
        logger.error("Failed to remove user {} from allocation with error {}".format(user_obj, e))
        return False

    try:
        allocation_remove_user.send(sender=sender, allocation_user_pk=allocation_user_obj.pk)
        actstream_action.send(requestor, verb='removed user from allocation', 
                                action_object=user_obj,target=allocation_obj.project)
    except Exception as e:
        logger.error("Failed to send signals on allocation user removal error: {}".format(e))

    return True