from __future__ import absolute_import
from __future__ import unicode_literals
import json

from django.http import HttpResponseBadRequest

from corehq.apps.app_manager.exceptions import (
    ScheduleError,
    ModuleNotFoundException)
from dimagi.utils.web import json_response
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    FormSchedule,
)
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps
import six


@no_conflict_require_POST
@require_can_edit_apps
def edit_schedule_phases(request, domain, app_id, module_unique_id):
    NEW_PHASE_ID = -1
    app = get_app(domain, app_id)

    try:
        module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        # temporary fallback
        module = app.get_module_by_id(module_unique_id)

    phases = json.loads(request.POST.get('phases'))
    changed_anchors = [(phase['id'], phase['anchor'])
                       for phase in phases if phase['id'] != NEW_PHASE_ID]
    all_anchors = [phase['anchor'] for phase in phases]
    enabled = json.loads(request.POST.get('has_schedule'))
    try:
        module.update_schedule_phase_anchors(changed_anchors)
        module.update_schedule_phases(all_anchors)
        module.has_schedule = enabled
    except ScheduleError as e:
        return HttpResponseBadRequest(six.text_type(e))

    response_json = {}
    app.save(response_json)
    return json_response(response_json)


@no_conflict_require_POST
@require_can_edit_apps
def edit_visit_schedule(request, domain, app_id, form_unique_id):
    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)
    module = form.get_module()

    json_loads = json.loads(request.POST.get('schedule'))
    enabled = json_loads.pop('enabled')
    anchor = json_loads.pop('anchor')
    schedule_form_id = json_loads.pop('schedule_form_id')

    if enabled:
        try:
            phase, is_new_phase = module.get_or_create_schedule_phase(anchor=anchor)
        except ScheduleError as e:
            return HttpResponseBadRequest(six.text_type(e))
        form.schedule_form_id = schedule_form_id
        form.schedule = FormSchedule.wrap(json_loads)
        phase.add_form(form)
    else:
        try:
            form.disable_schedule()
        except ScheduleError:
            pass

    response_json = {}
    app.save(response_json)
    return json_response(response_json)


def get_schedule_context(form):
    from corehq.apps.app_manager.models import SchedulePhase
    schedule_context = {}
    module = form.get_module()

    if not form.schedule:
        # Forms created before the scheduler module existed don't have this property
        # so we need to add it so everything works.
        form.schedule = FormSchedule(enabled=False)

    schedule_context.update({
        'all_schedule_phase_anchors': [phase.anchor for phase in module.get_schedule_phases()],
        'schedule_form_id': form.schedule_form_id,
    })

    if module.has_schedule:
        phase = form.get_phase()
        if phase is not None:
            schedule_context.update({'schedule_phase': phase})
        else:
            schedule_context.update({'schedule_phase': SchedulePhase(anchor='')})
    return schedule_context
