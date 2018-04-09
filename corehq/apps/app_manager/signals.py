from __future__ import absolute_import
from __future__ import unicode_literals
from django.dispatch.dispatcher import Signal


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
