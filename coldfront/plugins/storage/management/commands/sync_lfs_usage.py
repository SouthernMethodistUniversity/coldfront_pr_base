import logging
import pathlib
from datetime import datetime, timezone
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from coldfront.core.allocation.models import Allocation
from coldfront.plugins.storage.utils import (get_lfs_usage,
                                             STORAGE_ATTRIBUTE_NAME,
                                             STORAGE_GROUP_ATTRIBUTE_NAME,
                                             STORAGE_FILECOUNT_ATTRIBUTE_NAME,
                                             STORAGE_PATH_ATTRIBUTE_NAME)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync usage data from Lustre to ColdFront'

    def add_arguments(self, parser):

        parser.add_argument(
            "-s", "--sync", help="Update allocation attributes with latest data from Lustre", action="store_true")
        parser.add_argument(
            "-d", "--dryrun", help="Run with debugging output, but don't change any values", action="store_true")
        parser.add_argument(
            "-x", "--xdmod_data_folder", type=pathlib.Path,
            help="Generate an Xdmod data file for ingesting usage if a folder is provided")

    def handle(self, *args, **options):
        verbosity = int(options['verbosity'])
        root_logger = logging.getLogger('')
        if verbosity == 0:
            root_logger.setLevel(logging.ERROR)
        elif verbosity == 2:
            root_logger.setLevel(logging.INFO)
        elif verbosity == 3:
            root_logger.setLevel(logging.DEBUG)
        else:
            root_logger.setLevel(logging.WARN)

        self.dryrun = False
        if options['dryrun']:
            self.dryrun = True
            logger.warning("Using dryrun, no values will be updated")

        self.sync = False
        if options['sync']:
            self.sync = True
            logger.warning("Syncing ColdFront with Lustre")

        self.output = options["xdmod_data_folder"]
        if self.output:
            current_time_utc = datetime.now(timezone.utc)
            logger.debug("Saving xdmod data to {}".format(self.output))
        
        if self.sync or self.output:

            xdmod_data = []

            # get all storage allocations
            allocations = Allocation.objects.filter(resources__resource_type__name='Storage',
                                                    status__name__in=['Active'])
             
            for allocation in allocations:
                 updated = False

                 # skip deprecated projects
                 if (allocation.project.projectattribute_set.filter(value__in=['deprecated_work', 'deprecated_group']).distinct()):
                    continue
                 
                 for attribute in allocation.allocationattribute_set.all():
                    # only update the allocation once.
                    # it can find multiple usage attributes per allocation but we're updating them
                    # at the same time
                    if updated:
                        break
                    if attribute.allocation_attribute_type.has_usage:

                        project_id = str(allocation.get_attribute(STORAGE_GROUP_ATTRIBUTE_NAME))
                        project_path = ""
                        try:
                            project_path = str(allocation.get_attribute(STORAGE_PATH_ATTRIBUTE_NAME))
                            # we only need to the root path
                            project_path = '/' + project_path.split('/')[1]
                        except Exception as e:
                            logger.debug('Failed to get project path {} with error: {}'.format(project_id,e))

                        if self.dryrun:
                            logger.debug("checking lustre project id: {}".format(project_id))
                            
                        if project_path == "":
                            usage = get_lfs_usage(project_id)
                        else:
                            usage = get_lfs_usage(project_id, project_path)
                       
                        if usage:
                            
                            # returned in kB, convert to GB
                            try:
                                space_used = float(usage["space_used"]) / (1024 * 1024)
                                files_used = int(usage["files_used"])

                                # only used for xdmod, wants bytes
                                soft_space_quota = float(usage["space_quota"]) * 1024
                                hard_space_quota = float(usage["hard_space_quota"]) * 1024
                            except Exception as e:
                                logger.error('Failed to convert values for id {} with error: {} usage={}'.format(project_id,e,usage))
                            if not self.dryrun:

                                if self.sync:
                                    try:
                                        allocation.set_usage(STORAGE_ATTRIBUTE_NAME, space_used)
                                        allocation.set_usage(STORAGE_FILECOUNT_ATTRIBUTE_NAME, files_used)
                                        updated = True
                                    except Exception as e:
                                        logger.error("Failed to set usage for allocation {}, error: {}".format(allocation, e))
                                        continue
                                    
                                if self.output:

                                    # space in byte
                                    space_used = float(usage["space_used"]) * 1024
                                    tmp_entry = {
                                                "resource": "Work",
                                                "mountpoint": "/projects",
                                                "user": "combined_project_users",
                                                "pi": str(project_id),
                                                "dt": current_time_utc.strftime('%Y-%m-%dT%TZ'),
                                                "soft_threshold": int(soft_space_quota),
                                                "hard_threshold": int(hard_space_quota),
                                                "file_count": int(files_used),
                                                "logical_usage": int(space_used),
                                                "physical_usage": int(space_used)
                                    }
                                    xdmod_data.append(tmp_entry)
                            else:
                                logger.debug("simulating setting {} GB used and {} files for allocation: {}".format(space_used, files_used, allocation))

            
            if self.output and not self.dryrun:

                try:
                    filename = current_time_utc.strftime('%Y-%m-%dT%TZ') + '.json'
                    output_path = self.output.joinpath(filename)
                    logger.debug("Saving Xdmod data file to {}".format(output_path))
                    with output_path.open("w") as datafile:
                        json.dump(xdmod_data, datafile, indent=2)

                except Exception as e:
                    logger.error("Failed to write xdmod data file with error {}".format(e))
                            
