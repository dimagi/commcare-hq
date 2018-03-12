from __future__ import absolute_import

from __future__ import unicode_literals
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.motech.repeaters.models import CreateCaseRepeater, UpdateCaseRepeater
from couchforms.signals import successful_form_received

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.signals import commcare_user_post_save
from corehq.form_processor.models import CommCareCaseSQL


def create_form_repeat_records(sender, xform, **kwargs):
    from corehq.motech.repeaters.models import FormRepeater
    if not xform.is_duplicate:
        create_repeat_records(FormRepeater, xform)


def create_case_repeat_records(sender, case, **kwargs):
    from corehq.motech.repeaters.models import CaseRepeater
    create_repeat_records(CaseRepeater, case)
    create_repeat_records(CreateCaseRepeater, case)
    create_repeat_records(UpdateCaseRepeater, case)


def create_short_form_repeat_records(sender, xform, **kwargs):
    from corehq.motech.repeaters.models import ShortFormRepeater
    if not xform.is_duplicate:
        create_repeat_records(ShortFormRepeater, xform)


def create_repeat_records(repeater_cls, payload):
    repeater_name = repeater_cls.__module__ + '.' + repeater_cls.__name__
    if settings.REPEATERS_WHITELIST is not None and repeater_name not in settings.REPEATERS_WHITELIST:
        return
    domain = payload.domain
    if domain:
        repeaters = repeater_cls.by_domain(domain)
        for repeater in repeaters:
            repeater.register(payload)


@receiver(commcare_user_post_save, dispatch_uid="create_user_repeat_records")
def create_user_repeat_records(sender, couch_user, **kwargs):
    from corehq.motech.repeaters.models import UserRepeater
    create_repeat_records(UserRepeater, couch_user)


@receiver(post_save, sender=SQLLocation, dispatch_uid="create_location_repeat_records")
def create_location_repeat_records(sender, raw=False, **kwargs):
    from corehq.motech.repeaters.models import LocationRepeater
    if raw:
        return
    create_repeat_records(LocationRepeater, kwargs['instance'])


successful_form_received.connect(create_form_repeat_records)
successful_form_received.connect(create_short_form_repeat_records)
case_post_save.connect(create_case_repeat_records, CommCareCase)
case_post_save.connect(create_case_repeat_records, CommCareCaseSQL)
