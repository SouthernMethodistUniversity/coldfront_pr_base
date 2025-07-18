from django.dispatch import receiver

from coldfront.core.allocation.signals import allocation_activate_user
from coldfront.core.allocation.views import (AllocationAddUsersView,
                                             AllocationEULAView,
                                             AllocationDetailView)
from coldfront.core.project.views import (ProjectAddUsersView,
                                          ProjectCreateClassView)
from coldfront.core.utils.common import import_from_settings



@receiver(allocation_activate_user, sender=ProjectAddUsersView)
@receiver(allocation_activate_user, sender=ProjectCreateClassView)
@receiver(allocation_activate_user, sender=AllocationDetailView)
@receiver(allocation_activate_user, sender=AllocationAddUsersView)
@receiver(allocation_activate_user, sender=AllocationEULAView)
def activate_user(sender, **kwargs):
    allocation_user_pk = kwargs.get('allocation_user_pk')

    print("sender:", sender)
    print("activate allocation_user_pk", allocation_user_pk)