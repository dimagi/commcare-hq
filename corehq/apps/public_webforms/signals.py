from django.dispatch import receiver

from corehq.apps.app_manager.signals import app_post_save
from corehq.apps.public_webforms.models import PublicWebform


@receiver(app_post_save, dispatch_uid='close_deleted_app_public_webforms')
def close_deleted_app_public_webforms(sender, application, **kwargs):
    if application.is_deleted():
        PublicWebform.objects.filter(
            domain=application.domain, app_id=application.id).update(is_disabled=True)
