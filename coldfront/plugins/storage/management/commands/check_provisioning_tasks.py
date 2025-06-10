import logging
import os

from django.core.management.base import BaseCommand, CommandError

from coldfront.plugins.storage.utils import (check_for_completed_storage_tasks
                                             )

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check for completed Storage Provisioning tasks'

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

        check_for_completed_storage_tasks()
        

