from django.db.models.signals import post_save
from django.dispatch import receiver

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from couchforms.signals import successful_form_received

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.signals import commcare_user_post_save
from corehq.form_processor.models import CommCareCaseSQL


def create_form_repeat_records(sender, xform, **kwargs):
    from corehq.apps.repeaters.models import FormRepeater
    create_repeat_records(FormRepeater, xform)


def create_case_repeat_records(sender, case, **kwargs):
    from corehq.apps.repeaters.models import CaseRepeater
    create_repeat_records(CaseRepeater, case)


def create_short_form_repeat_records(sender, xform, **kwargs):
    from corehq.apps.repeaters.models import ShortFormRepeater
    create_repeat_records(ShortFormRepeater, xform)


def create_repeat_records(repeater_cls, payload):
    domain = payload.domain
    if domain:
        repeaters = repeater_cls.by_domain(domain)
        for repeater in repeaters:
            repeater.register(payload)


@receiver(commcare_user_post_save, dispatch_uid="create_user_repeat_records")
def create_user_repeat_records(sender, couch_user, **kwargs):
    from corehq.apps.repeaters.models import UserRepeater
    create_repeat_records(UserRepeater, couch_user)


@receiver(post_save, sender=SQLLocation, dispatch_uid="create_location_repeat_records")
def create_location_repeat_records(sender, raw=False, **kwargs):
    from corehq.apps.repeaters.models import LocationRepeater
    if raw:
        return
    create_repeat_records(LocationRepeater, kwargs['instance'])


successful_form_received.connect(create_form_repeat_records)
successful_form_received.connect(create_short_form_repeat_records)
case_post_save.connect(create_case_repeat_records, CommCareCase)
case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)
