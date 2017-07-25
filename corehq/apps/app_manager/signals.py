from django.dispatch.dispatcher import Signal

from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.const import CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.app_manager.models import CareplanModule, CareplanConfig, CareplanAppProperties


def create_app_structure_repeat_records(sender, application, **kwargs):
    from corehq.motech.repeaters.models import AppStructureRepeater
    domain = application.domain
    if domain:
        repeaters = AppStructureRepeater.by_domain(domain)
        for repeater in repeaters:
            repeater.register(application)


app_post_save = Signal(providing_args=['application'])

app_post_save.connect(create_app_structure_repeat_records)

app_post_release = Signal(providing_args=['application'])
