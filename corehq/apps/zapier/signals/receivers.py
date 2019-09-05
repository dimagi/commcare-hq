from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from tastypie.exceptions import ImmediateHttpResponse
from tastypie.http import HttpBadRequest

from corehq.apps.zapier.consts import CASE_TYPE_REPEATER_CLASS_MAP, EventTypes
from corehq.apps.zapier.models import ZapierSubscription
from corehq.motech.repeaters.models import FormRepeater


@receiver(pre_save, sender=ZapierSubscription)
def zapier_subscription_pre_save(sender, instance, *args, **kwargs):
    """
    Creates a repeater object corresponding to the type of trigger (form or case)
    """
    if instance.pk:
        return

    if instance.event_name == EventTypes.NEW_FORM:
        repeater = FormRepeater(
            domain=instance.domain,
            url=instance.url,
            format='form_json',
            include_app_id_param=False,
            white_listed_form_xmlns=[instance.form_xmlns]
        )

    elif instance.event_name in CASE_TYPE_REPEATER_CLASS_MAP:
        repeater = CASE_TYPE_REPEATER_CLASS_MAP[instance.event_name](
            domain=instance.domain,
            url=instance.url,
            format='case_json',
            white_listed_case_types=[instance.case_type],
        )
    else:
        raise ImmediateHttpResponse(
            HttpBadRequest('The passed event type is not valid.')
        )

    repeater.save()
    instance.repeater_id = repeater.get_id


@receiver(post_delete, sender=ZapierSubscription)
def zapier_subscription_post_delete(sender, instance, *args, **kwargs):
    """
    Deletes the repeater object when the corresponding zap is turned off
    """
    if instance.event_name == EventTypes.NEW_FORM:
        repeater = FormRepeater.get(instance.repeater_id)
    elif instance.event_name in CASE_TYPE_REPEATER_CLASS_MAP:
        repeater = CASE_TYPE_REPEATER_CLASS_MAP[instance.event_name].get(instance.repeater_id)
    else:
        raise ImmediateHttpResponse(
            HttpBadRequest('The passed event type is not valid.')
        )
    repeater.delete()
