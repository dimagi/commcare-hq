import uuid

from django.db import migrations, models
from django.forms.models import model_to_dict

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.events.models import (
    EVENT_ATTENDEE_CASE_TYPE,
    EVENT_CASE_TYPE,
    get_attendee_case_type,
)
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex


def _recreate_events(apps, schema_editor):
    """
    Avoids orphaned event cases
    """
    # This Event model only has data, no properties or methods, which is
    # why we need all the functions below.
    Event = apps.get_model("events", "Event")
    db_alias = schema_editor.connection.alias
    for event in Event.objects.using(db_alias).all():
        case_factory = CaseFactory(domain=event.domain)
        event_dict = model_to_dict(event)
        attendees = _get_expected_attendees(event)
        _delete_old_style(case_factory, event)

        new_event = Event(**event_dict)
        new_event.save()
        _set_expected_attendees(case_factory, new_event, attendees)


def _get_old_case_id(event):
    return event.event_id.hex + '-0'


def _get_expected_attendees(event):
    old_case_id = _get_old_case_id(event)
    ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
        event.domain,
        [old_case_id],
        include_closed=False,
    )
    return CommCareCase.objects.get_cases(ext_case_ids, event.domain)


def _delete_old_style(case_factory, event):
    old_case_id = _get_old_case_id(event)
    _close_ext_cases(case_factory, event)
    case_factory.close_case(old_case_id)
    event.delete()


def _close_ext_cases(case_factory, event):
    old_case_id = _get_old_case_id(event)
    ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
        event.domain,
        [old_case_id],
        include_closed=False,
    )
    case_factory.create_or_update_cases([
        CaseStructure(case_id=case_id, attrs={'close': True})
        for case_id in ext_case_ids
    ])


def _set_expected_attendees(case_factory, event, attendees):
    event_case_id = event._case_id.hex
    event_group_id = event.event_id.hex
    attendee_case_type = get_attendee_case_type(event.domain)
    attendee_case_ids = (c.case_id for c in attendees)
    case_structures = []
    for case_id in attendee_case_ids:
        event_host = CaseStructure(case_id=event_case_id)
        attendee_host = CaseStructure(case_id=case_id)
        case_structures.append(CaseStructure(
            indices=[
                CaseIndex(
                    relationship='extension',
                    identifier='event-host',
                    related_structure=event_host,
                    related_type=EVENT_CASE_TYPE,
                ),
                CaseIndex(
                    relationship='extension',
                    identifier='attendee-host',
                    related_structure=attendee_host,
                    related_type=attendee_case_type,
                ),
            ],
            attrs={
                'case_type': EVENT_ATTENDEE_CASE_TYPE,
                'owner_id': event_group_id,
                'create': True,
            },
        ))
    case_factory.create_or_update_cases(case_structures)


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0003_event_attendance_taker_ids'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='event',
            name='commcare_ev_event_i_c27a78_idx',
        ),
        migrations.RemoveField(
            model_name='event',
            name='id',
        ),
        migrations.AddField(
            model_name='event',
            name='_case_id',
            field=models.UUIDField(default=uuid.uuid4),
        ),
        migrations.AlterField(
            model_name='event',
            name='event_id',
            field=models.UUIDField(
                default=uuid.uuid4,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.RunPython(
            _recreate_events,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
