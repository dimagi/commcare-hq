import json
import logging

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from couchdbkit.exceptions import ResourceConflict
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.conf import settings
from django.contrib import messages
from corehq.apps.app_manager.app_schemas.casedb_schema import get_casedb_schema
from corehq.apps.app_manager.app_schemas.session_schema import get_session_schema

from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.views.apps import get_apps_base_context
from corehq.apps.app_manager.views.notifications import get_facility_for_form, notify_form_opened

from corehq.apps.app_manager.exceptions import AppManagerException

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
    get_app_manager_template,
    app_callout_templates,
    is_usercase_in_use,
)
from corehq.apps.cloudcare.utils import should_show_preview_app
from corehq.apps.fixtures.fixturegenerators import item_lists_by_domain
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    Form,
    ModuleNotFoundException,
)
from corehq.apps.app_manager.decorators import require_can_edit_apps
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.analytics.tasks import track_entered_form_builder_on_hubspot
from corehq.apps.analytics.utils import get_meta
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import cachebuster
from corehq.apps.tour import tours
from corehq.apps.analytics import ab_tests
from corehq.apps.domain.models import Domain
from corehq.util.context_processors import websockets_override


logger = logging.getLogger(__name__)


@require_can_edit_apps
def form_designer(request, domain, app_id, module_id=None, form_id=None):

    def _form_uses_case(module, form):
        return (
            (module and module.case_type and form.requires_case()) or
            is_usercase_in_use(domain)
        )

    def _form_is_basic(form):
        return form.doc_type == 'Form'

    def _form_too_large(app, form):
        # form less than 0.1MB, anything larger starts to have
        # performance issues with fullstory
        return app.blobs['{}.xml'.format(form.unique_id)]['content_length'] > 102400

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
                            form_unique_id=form.unique_id)

    include_fullstory = False
    vellum_plugins = ["modeliteration", "itemset", "atwho"]
    if (toggles.COMMTRACK.enabled(domain)):
        vellum_plugins.append("commtrack")
    if toggles.VELLUM_SAVE_TO_CASE.enabled(domain):
        vellum_plugins.append("saveToCase")
    if (_form_uses_case(module, form) and _form_is_basic(form)):
        vellum_plugins.append("databrowser")

    vellum_features = toggles.toggles_dict(username=request.user.username,
                                           domain=domain)
    vellum_features.update(feature_previews.previews_dict(domain))
    include_fullstory = not _form_too_large(app, form)
    vellum_features.update({
        'group_in_field_list': app.enable_group_in_field_list,
        'image_resize': app.enable_image_resize,
        'markdown_in_groups': app.enable_markdown_in_groups,
        'lookup_tables': domain_has_privilege(domain, privileges.LOOKUP_TABLES),
        'templated_intents': domain_has_privilege(domain, privileges.TEMPLATED_INTENTS),
        'custom_intents': domain_has_privilege(domain, privileges.CUSTOM_INTENTS),
        'rich_text': True,
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
        'include_fullstory': include_fullstory,
    })
    notify_form_opened(domain, request.couch_user, app_id, form.unique_id)

    domain_obj = Domain.get_by_name(domain)
    context.update({
        'show_live_preview': should_show_preview_app(
            request,
            app,
            request.couch_user.username,
        ),
        'can_preview_form': request.couch_user.has_permission(domain, 'edit_data'),
    })

    core = {
        'dataSourcesEndpoint': reverse('get_form_data_schema',
            kwargs={'domain': domain, 'form_unique_id': form.get_unique_id()}),
        'dataSource': [
            # DEPRECATED. Use dataSourcesEndpoint
            {
                'key': 'fixture',
                'name': 'Fixtures',
                'endpoint': reverse('fixture_metadata', kwargs={'domain': domain}),
            },
        ],
        'form': form.source,
        'formId': form.get_unique_id(),
        'formName': trans(form.name, app.langs),
        'saveType': 'patch',
        'saveUrl': reverse('edit_form_attr', args=[domain, app.id, form.get_unique_id(), 'xform']),
        'patchUrl': reverse('patch_xform', args=[domain, app.id, form.get_unique_id()]),
        'allowedDataNodeReferences': [
            "meta/deviceID",
            "meta/instanceID",
            "meta/username",
            "meta/userID",
            "meta/timeStart",
            "meta/timeEnd",
            "meta/location",
        ] + scheduler_data_nodes,
        'activityUrl': reverse('ping'),
        'sessionid': request.COOKIES.get('sessionid'),
        'externalLinks': {
            'changeSubscription': reverse("domain_subscription_view", kwargs={'domain': domain}),
        },
        'invalidCaseProperties': ['name'],
    }

    if toggles.APP_MANAGER_V2.enabled(request.user.username):
        if form.get_action_type() == 'open':
            core.update({
                'defaultHelpTextTemplateId': '#fd-hq-helptext-registration',
                'formIconClass': 'fcc fcc-app-createform',
            })
        elif form.get_action_type() == 'close':
            core.update({
                'defaultHelpTextTemplateId': '#fd-hq-helptext-close',
                'formIconClass': 'fcc fcc-app-completeform',
            })
        elif form.get_action_type() == 'update':
            core.update({
                'defaultHelpTextTemplateId': '#fd-hq-helptext-followup',
                'formIconClass': 'fcc fcc-app-updateform',
            })
        else:
            core.update({
                'defaultHelpTextTemplateId': '#fd-hq-helptext-survey',
                'formIconClass': 'fa fa-file-o',
            })

    vellum_options = {
        'core': core,
        'plugins': vellum_plugins,
        'features': vellum_features,
        'intents': {
            'templates': next(app_callout_templates),
        },
        'javaRosa': {
            'langs': app.langs,
            'displayLanguage': context['lang'],
        },
        'uploader': {
            'uploadUrls': {
                'image': reverse("hqmedia_uploader_image", args=[domain, app.id]),
                'audio': reverse("hqmedia_uploader_audio", args=[domain, app.id]),
                'video': reverse("hqmedia_uploader_video", args=[domain, app.id]),
                'text': reverse("hqmedia_uploader_text", args=[domain, app.id]),
            },
            'objectMap': app.get_object_map(),
            'sessionid': request.COOKIES.get('sessionid'),
        },
    }
    context.update({
        'vellum_options': vellum_options,
        'CKEDITOR_BASEPATH': "app_manager/js/vellum/lib/ckeditor/",
    })

    if request.user.is_superuser:
        notification_options = websockets_override(request)
        if notification_options['WS4REDIS_HEARTBEAT'] in ['null', 'undefined']:
            notification_options['WS4REDIS_HEARTBEAT'] = None
        notification_options.update({
            'notify_facility': get_facility_for_form(domain, app_id, form.unique_id),
            'user_id': request.couch_user.get_id,
        })
        context.update({'notification_options': notification_options})

    if not settings.VELLUM_DEBUG:
        context.update({'requirejs_url': "app_manager/js/vellum/src"})
    elif settings.VELLUM_DEBUG == "dev-min":
        context.update({'requirejs_url': "formdesigner/_build/src"})
    else:
        context.update({'requirejs_url': "formdesigner/src"})

    context['current_app_version_url'] = reverse('current_app_version', args=[domain, app_id])

    context.update({
        'requirejs_args': 'version={}{}'.format(
            cachebuster("app_manager/js/vellum/src/main-components.js"),
            cachebuster("app_manager/js/vellum/src/local-deps.js")
        ),
    })

    template = get_app_manager_template(
        request.user,
        'app_manager/v1/form_designer.html',
        'app_manager/v2/form_designer.html',
    )

    response = render(request, template, context)
    return response


@require_GET
@require_can_edit_apps
def get_form_data_schema(request, domain, form_unique_id):
    """Get data schema

    One of `app_id` or `form_unique_id` is required. `app_id` is ignored
    if `form_unique_id` is provided.

    :returns: A list of data source schema definitions. A data source schema
    definition is a dictionary. For details on the content of the dictionary,
    see https://github.com/dimagi/Vellum/blob/master/src/datasources.js
    """
    data = []

    try:
        form, app = Form.get_form(form_unique_id, and_app=True)
    except ResourceConflict:
        raise Http404()

    if app.domain != domain:
        raise Http404()

    try:
        data.append(get_session_schema(form))
        if form.requires_case() or is_usercase_in_use(domain):
            data.append(get_casedb_schema(form))
    except AppManagerException as e:
        notify_exception(request, message=e.message)
        return HttpResponseBadRequest(_(
            "There is an error in the case management of your application. "
            "Please fix the error to see case properties in this tree"
        ))
    except Exception as e:
        notify_exception(request, message=e.message)
        return HttpResponseBadRequest("schema error, see log for details")

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
