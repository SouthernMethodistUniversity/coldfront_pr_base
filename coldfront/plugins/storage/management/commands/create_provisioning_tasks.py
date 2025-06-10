import logging
import os
import time
from datetime import datetime, timezone, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from coldfront.core.utils.mail import send_provision_error_admin_email

from coldfront.plugins.storage.utils import (create_new_storage_tasks
                                             )
from coldfront.plugins.smu_ext.utils import create_account_provisioning_task
from coldfront.core.user.models import UserProfile

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Create Tasks for Storage Provisioning'


    def add_arguments(self, parser):
        parser.add_argument(
            "-d", "--delay", help="Specify the delay to stagger the launch of provisioning tasks")
        parser.add_argument(
            "-r", "--recheck", help="Specify the delay between trying to reprovision, in minutes.")

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

        self.delay = 0
        if options['delay']:
            self.delay = int(options['delay'])
            
        self.repeated_checks = 3
        
        self.recheck_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        if options['recheck']:
            self.recheck_time = datetime.now(timezone.utc) - timedelta(minutes=float(options['recheck']))

        unprovisioned_users = create_new_storage_tasks()

        for username in unprovisioned_users:
            userobj = User.objects.get(username=username)
            userprofile = UserProfile.objects.get(user=userobj)
            
            n_m3_validation_error = 0
            hist_obj = userprofile.history.first()
            for i in range(0, self.repeated_checks):
                try:
                    if hist_obj.m3_account_validation == '4':
                        n_m3_validation_error += 1
                    hist_obj = hist_obj.prev_record
                except:
                    pass
                
            recheck = True
            if n_m3_validation_error == self.repeated_checks:
                recheck = False
                send_provision_error_admin_email(userobj, "M3 shell error", "email/provisioning_error.txt")
                userprofile.m3_account_validation = '5'
                userprofile.save()
                
            if userprofile.m3_account_validation == '5':
                recheck = False
                
            if recheck and userprofile.history.first().history_date < self.recheck_time:
                logger.debug('Creating account for user {} (last update {}, eligible to check {})'.format(username, userprofile.history.first().history_date, self.recheck_time))
                create_account_provisioning_task(username)
                time.sleep(self.delay)


        

