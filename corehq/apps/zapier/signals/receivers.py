from django.dispatch import receiver

from corehq.apps.zapier.tasks import send_to_subscribers_task
from corehq.toggles import ZAPIER_INTEGRATION
from couchforms.signals import successful_form_received


@receiver(successful_form_received)
def send_form_subscribers(sender, xform, *args, **kwargs):
    domain = xform.domain
    if not ZAPIER_INTEGRATION.enabled(domain):
        return
    send_to_subscribers_task.delay(domain, xform)
