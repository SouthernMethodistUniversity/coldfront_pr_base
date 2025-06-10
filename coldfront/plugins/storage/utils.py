import logging
import json
import pathlib
import re
import datetime

from coldfront.core.utils.common import import_from_settings

from coldfront.core.allocation.models import (Allocation,
                                              AllocationUser,
                                              AllocationStatusChoice,
                                              AllocationUserStatusChoice,
                                              AllocationUserStorageStatusChoice,
                                              AllocationUserStoragePermissionChoice)
from coldfront.core.user.models import UserProfile


STORAGE_STAGING_QUEUE_PATH = import_from_settings('STORAGE_STAGING_QUEUE_PATH', '')
STORAGE_STAGING_RUNNING_PATH = import_from_settings('STORAGE_STAGING_RUNNING_PATH', '')
STORAGE_STAGING_COMPLETED_PATH = import_from_settings('STORAGE_STAGING_COMPLETED_PATH', '')
STORAGE_STAGING_ARCHIVE_PATH = import_from_settings('STORAGE_STAGING_ARCHIVE_PATH', '')
STORAGE_LFS_COMMAND = import_from_settings('STORAGE_LFS_COMMAND', '')
STORAGE_ATTRIBUTE_NAME = import_from_settings('STORAGE_ATTRIBUTE_NAME', 'Storage Quota (GB)')
STORAGE_FILECOUNT_ATTRIBUTE_NAME = import_from_settings('STORAGE_FILECOUNT_ATTRIBUTE_NAME', 'Storage Quota (File Count)')
STORAGE_GROUP_ATTRIBUTE_NAME = import_from_settings('STORAGE_GROUP_ATTRIBUTE_NAME', 'Storage Project ID')
STORAGE_PATH_ATTRIBUTE_NAME = import_from_settings('STORAGE_PATH_ATTRIBUTE_NAME', 'Storage Path')


logger = logging.getLogger(__name__)

class StorageError(Exception):
    pass

def get_storage_task_ids(staging_dir):
    tasks = []
    if staging_dir:
        task_files = pathlib.Path(staging_dir).joinpath().glob("*.json")
        for p in task_files:
            task_id = re.findall(r'\.*taskid_(\d+)', str(p))
            if task_id:
                tasks.append(task_id[0])
    return tasks

def get_storage_task_dependency_ids(staging_dir):
    tasks = []
    if staging_dir:
        task_files = pathlib.Path(staging_dir).joinpath().glob("*.json")
        for p in task_files:
            if "dependent" in p:
                with open(p) as json_file:
                    json_text = json.load(json_file)
                    tasks = tasks + json_text['cf_task_dependencies']
    return tasks

def get_storage_allocations(status):

    if type(status) is not list:
        status = [status]

    unprovisioned_allocations = AllocationUser.objects.filter(
            allocation__status__name='Active',
            storage_status__name__in=status, 
            allocation__resources__resource_type__name='Storage')
        
    return unprovisioned_allocations

def create_new_storage_tasks():

    unprovisioned_users = []

    # get new storage allocation requests
    new_allocations = get_storage_allocations(['New', 'UpdateQuota', 'NewPermissions', 'ChangePermissions'])

    allocation_user_active_status = AllocationUserStatusChoice.objects.get(
            name='Active')
    allocation_user_removed_status = AllocationUserStatusChoice.objects.get(
            name='Removed')
    
    # restrict to active allocations
    # also include "removed" as we may need to remove permissions
    # from an user who is no longer active
    new_allocations = new_allocations.filter(status__in=[allocation_user_active_status,
                                                         allocation_user_removed_status]).order_by('allocation_id')

    read_only = AllocationUserStoragePermissionChoice.objects.get(name='Read Only')
    readwrite = AllocationUserStoragePermissionChoice.objects.get(name='Read and Write')
    no_permissions = AllocationUserStoragePermissionChoice.objects.get(name='None')
    provisioned_status = AllocationUserStorageStatusChoice.objects.get(name='Provisioned')
    pending_status = AllocationUserStorageStatusChoice.objects.get(name='Pending')

    # create a task for each user+allocation
    active_allocation_status = AllocationStatusChoice.objects.get(name='Active')
    new_allocations = list(new_allocations)
    for allocation in new_allocations:
        
        current_allocation_id = allocation.allocation_id
        current_allocation_obj = Allocation.objects.get(pk=current_allocation_id)

        try:
            userprofile = UserProfile.objects.get(user=allocation.user)
            if userprofile.m3_account_validation != '2' and allocation.status != allocation_user_removed_status:
                unprovisioned_users.append(allocation.user.username)
                continue
        except Exception as e:
            logger.error('Error checking userprofile: {}'.format(e))
            continue


        # only process active allocations
        if current_allocation_obj.status == active_allocation_status:

            current_pi = current_allocation_obj.project.pi
            pi_allocation_status = AllocationUser.objects.get(allocation_id=current_allocation_id, user=current_pi)
            
            if (pi_allocation_status.storage_status == provisioned_status) or (current_pi.username == allocation.user.username):
                dependent_tasks = []
            else:
                # if PI is not provisioned, they must go before other users
                dependent_tasks = [str(pi_allocation_status.pk).zfill(9) + '1' + str(1).zfill(8)]

            # figure out how many tasks have been previously run
            ntasks = len(allocation.history.filter(storage_status__name="Provisioned")) + 1

            alloc_attr_set = list(current_allocation_obj.get_attribute_set(allocation.user))
            task_data = {}
            if (current_pi.username == allocation.user.username):
                if (allocation.storage_status.name == "New"):
                    task_data["task_type"] = "new allocation, provision space and permissions for PI"
                elif (allocation.storage_status.name == "UpdateQuota"):
                    task_data["task_type"] = "update quotas for PI"
                elif (allocation.storage_status.name == "ChangePermissions"):
                    task_data["task_type"] = "change permissions for PI"
                elif (allocation.storage_status.name == "NewPermissions"):
                    task_data["task_type"] = "change permissions for PI"
            else:
                if (allocation.storage_status.name == "New"):
                    task_data["task_type"] = "new allocation, add user"
                elif (allocation.storage_status.name == "ChangePermissions"):
                    task_data["task_type"] = "change permissions on existing user"
                elif (allocation.storage_status.name == "NewPermissions"):
                    task_data["task_type"] = "add permission for a new user"
                elif (allocation.storage_status.name == "UpdateQuota"):
                    task_data["task_type"] = "update quotas for user"                
            task_data["system"] = current_allocation_obj.resources.first().name
            for attr in alloc_attr_set:
                if (attr.allocation_attribute_type.name == STORAGE_GROUP_ATTRIBUTE_NAME):
                    task_data["lustre_pid"] = attr.value
                if (attr.allocation_attribute_type.name == STORAGE_FILECOUNT_ATTRIBUTE_NAME):
                    task_data["file_quota"] = attr.value
                if (attr.allocation_attribute_type.name == STORAGE_ATTRIBUTE_NAME):
                    task_data["capacity_quota"] = attr.value
                if (attr.allocation_attribute_type.name == STORAGE_PATH_ATTRIBUTE_NAME):
                    task_data["path"] = attr.value
            task_data['user'] = allocation.user.username
        
            cur_perms = AllocationUserStoragePermissionChoice.objects.get(allocationuser=allocation)



            if (cur_perms == no_permissions):
                task_data['permissions'] = "none"
            elif (cur_perms == read_only):
                task_data['permissions'] = "rx"
            elif (cur_perms == readwrite):
                task_data['permissions'] = "rwx"
            if (allocation.status == allocation_user_removed_status) and (cur_perms != no_permissions):
                logger.warning("Allocation user {} is removed but has {} permissions".format(allocation.user.username, cur_perms))
            task_data["cf_task_id"] = str(allocation.pk).zfill(9) + '1' + str(ntasks).zfill(8)
            if dependent_tasks:
                task_data['dependent_tasks'] = dependent_tasks

            task_file_path = ""
            if (allocation.storage_status.name == "New"):
                task_file_path = pathlib.Path(STORAGE_STAGING_QUEUE_PATH).joinpath("new_allocation_taskid_" + task_data["cf_task_id"] + ".json")
            elif (allocation.storage_status.name == "ChangePermissions"):
                task_file_path = pathlib.Path(STORAGE_STAGING_QUEUE_PATH).joinpath("change_permissions_taskid_" + task_data["cf_task_id"] + ".json")
            elif (allocation.storage_status.name == "NewPermissions"):
                task_file_path = pathlib.Path(STORAGE_STAGING_QUEUE_PATH).joinpath("new_permissions_taskid_" + task_data["cf_task_id"] + ".json")
            elif (allocation.storage_status.name == "UpdateQuota"):
                task_file_path = pathlib.Path(STORAGE_STAGING_QUEUE_PATH).joinpath("update_quota_taskid_" + task_data["cf_task_id"] + ".json")
            if task_file_path:
                with open(task_file_path, 'w') as f:
                    json.dump(task_data, f, indent=2)

            allocation.storage_status = pending_status
            allocation.save()

    unprovisioned_users = list(set(unprovisioned_users))
    return unprovisioned_users

def check_for_completed_storage_tasks():

    provisioned_status = AllocationUserStorageStatusChoice.objects.get(name='Provisioned')
    if STORAGE_STAGING_COMPLETED_PATH and STORAGE_STAGING_ARCHIVE_PATH:
        task_files = pathlib.Path(STORAGE_STAGING_COMPLETED_PATH).joinpath().glob("*.json")
        for p in task_files:
            task_id = re.findall(r'\.*taskid_(\d+)', str(p))
            if task_id:
                task_id = task_id[0]
                user_pk = int(task_id[0:9])

                try:
                    UserAllocation = AllocationUser.objects.get(id=user_pk)
                    UserAllocation.storage_status = provisioned_status
                    UserAllocation.save()

                    # add date and archive
                    filename = str(p.stem) + "_completed_" + datetime.datetime.now().strftime("%m%d%Y-%H%M%S") + ".json"
                    new_path = pathlib.Path(STORAGE_STAGING_ARCHIVE_PATH).joinpath(filename)
                    p.replace(new_path)
                except Exception as e:
                    logger.error("failed to update task {} for user_pk {} with error {}".format(task_id, user_pk, e))
