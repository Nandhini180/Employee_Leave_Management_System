from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LeaveRequest
from .services import email_manager_on_new_request


@receiver(post_save, sender=LeaveRequest)
def notify_manager_for_new_request(sender, instance, created, **kwargs):
    if created and instance.status == LeaveRequest.Status.PENDING:
        email_manager_on_new_request(instance)
