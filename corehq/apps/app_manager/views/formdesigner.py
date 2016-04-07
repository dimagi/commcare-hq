import json
import logging

from django.utils.translation import ugettext as _
from couchdbkit.exceptions import ResourceConflict
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.conf import settings
from django.contrib import messages
from corehq.apps.app_manager.views.apps import get_apps_base_context

from corehq.apps.app_manager.views.utils import back_to_main, bail
from corehq import toggles, privileges, feature_previews
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.const import (
    SCHEDULE_CURRENT_VISIT_NUMBER,
    SCHEDULE_NEXT_DUE,
    SCHEDULE_UNSCHEDULED_VISIT,
    SCHEDULE_GLOBAL_NEXT_VISIT_DATE,
)
from corehq.apps.app_manager.util import (
    get_casedb_schema,
    get_session_schema,
    app_callout_templates,
)
from corehq.apps.fixtures.fixturegenerators import item_lists_by_domain
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    Form,
    ModuleNotFoundException,
)
from corehq.apps.app_manager.decorators import require_can_edit_apps
from corehq.apps.analytics.tasks import track_entered_form_builder_on_hubspot
from corehq.apps.analytics.utils import get_meta


logger = logging.getLogger(__name__)


@require_can_edit_apps
def form_designer(request, domain, app_id, module_id=None, form_id=None):
    meta = get_meta(request)
    track_entered_form_builder_on_hubspot.delay(request.couch_user, request.COOKIES, meta)

    app = get_app(domain, app_id)
    module = None

    try:
        module = app.get_module(module_id)
    except ModuleNotFoundException:
        return bail(request, domain, app_id, not_found="module")
    try:
        form = module.get_form(form_id)
    except IndexError:
        return bail(request, domain, app_id, not_found="form")

    if form.no_vellum:
        messages.warning(request, _(
            "You tried to edit this form in the Form Builder. "
            "However, your administrator has locked this form against editing "
            "in the form builder, so we have redirected you to "
            "the form's front page instead."
        ))
        return back_to_main(request, domain, app_id=app_id,
                            unique_form_id=form.unique_id)

    vellum_plugins = ["modeliteration", "itemset", "atwho"]
    if (toggles.COMMTRACK.enabled(domain)):
        vellum_plugins.append("commtrack")
    if toggles.VELLUM_SAVE_TO_CASE.enabled(domain):
        vellum_plugins.append("saveToCase")
    if toggles.VELLUM_EXPERIMENTAL_UI.enabled(domain) and module and module.case_type and form.requires_case():
        vellum_plugins.append("databrowser")

    vellum_features = toggles.toggles_dict(username=request.user.username,
                                           domain=domain)
    vellum_features.update(feature_previews.previews_dict(domain))
    vellum_features.update({
        'group_in_field_list': app.enable_group_in_field_list,
        'image_resize': app.enable_image_resize,
        'markdown_in_groups': app.enable_markdown_in_groups,
        'lookup_tables': domain_has_privilege(domain, privileges.LOOKUP_TABLES),
        'templated_intents': domain_has_privilege(domain, privileges.TEMPLATED_INTENTS),
        'custom_intents': domain_has_privilege(domain, privileges.CUSTOM_INTENTS),
    })

    has_schedule = (
        getattr(module, 'has_schedule', False) and
        getattr(form, 'schedule', False) and form.schedule.enabled
    )
    scheduler_data_nodes = []
    if has_schedule:
        scheduler_data_nodes = [
            SCHEDULE_CURRENT_VISIT_NUMBER,
            SCHEDULE_NEXT_DUE,
            SCHEDULE_UNSCHEDULED_VISIT,
            SCHEDULE_GLOBAL_NEXT_VISIT_DATE,
        ]
        scheduler_data_nodes.extend([
            u"next_{}".format(f.schedule_form_id)
            for f in form.get_phase().get_forms()
            if getattr(f, 'schedule', False) and f.schedule.enabled
        ])


    context = get_apps_base_context(request, domain, app)
    context.update(locals())
    context.update({
        'vellum_debug': settings.VELLUM_DEBUG,
        'nav_form': form,
        'formdesigner': True,
        'multimedia_object_map': app.get_object_map(),
        'sessionid': request.COOKIES.get('sessionid'),
        'features': vellum_features,
        'plugins': vellum_plugins,
        'app_callout_templates': next(app_callout_templates),
        'scheduler_data_nodes': scheduler_data_nodes,
        'no_header': True,
    })
    return render(request, 'app_manager/form_designer.html', context)


@require_GET
@require_can_edit_apps
def get_form_data_schema(request, domain, form_unique_id):
    """Get data schema

    One of `app_id` or `form_unique_id` is required. `app_id` is ignored
    if `form_unique_id` is provided.

    :returns: A list of data source schema definitions. A data source schema
    definition is a dictionary with the following format:
    ```
    {
        "id": string (default instance id)
        "uri": string (instance src)
        "path": string (path of root nodeset, not including `instance(...)`)
        "name": string (human readable name)
        "structure": {
            element: {
                "name": string (optional human readable name)
                "structure": {
                    nested-element: { ... }
                },
            },
            ref-element: {
                "reference": {
                    "source": string (optional data source id, defaults to this data source)
                    "subset": string (optional subset id)
                    "key": string (referenced property)
                }
            },
            @attribute: { },
            ...
        },
        "subsets": [
            {
                "id": string (unique identifier for this subset)
                "key": string (unique identifier property name)
                "name": string (optional human readable name)
                "structure": { ... }
                "related": {
                    string (relationship): string (related subset name),
                    ...
                }
            },
            ...
        ]
    }
    ```
    A structure may contain nested structure elements. A nested element
    may contain one of "structure" (a concrete structure definition) or
    "reference" (a link to some other structure definition). Any
    structure item may have a human readable "name".
    """
    data = []

    try:
        form, app = Form.get_form(form_unique_id, and_app=True)
    except ResourceConflict:
        raise Http404()
    data.append(get_session_schema(form))

    if app.domain != domain:
        raise Http404()
    if form and form.requires_case():
        data.append(get_casedb_schema(app))  # TODO use domain instead of app
    data.extend(
        sorted(item_lists_by_domain(domain), key=lambda x: x['name'].lower())
    )
    kw = {}
    if "pretty" in request.GET:
        kw["indent"] = 2
    return HttpResponse(json.dumps(data, **kw))


@require_GET
def ping(request):
    return HttpResponse("pong")
