from datetime import datetime, timedelta
import json
import logging
from looseversion import LooseVersion

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from dimagi.utils.logging import notify_exception

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import (
    HUBSPOT_FORM_BUILDER_FORM_ID,
    send_hubspot_form,
)
from corehq.apps.app_manager import add_ons
from corehq.apps.app_manager.app_schemas.casedb_schema import get_casedb_schema, get_registry_schema
from corehq.apps.app_manager.app_schemas.session_schema import (
    get_session_schema,
)
from corehq.apps.app_manager.const import (
    SCHEDULE_CURRENT_VISIT_NUMBER,
    SCHEDULE_GLOBAL_NEXT_VISIT_DATE,
    SCHEDULE_NEXT_DUE,
    SCHEDULE_UNSCHEDULED_VISIT,
)
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import require_can_edit_apps
from corehq.apps.app_manager.exceptions import (
    AppManagerException,
    FormNotFoundException,
)
from corehq.apps.app_manager.models import ModuleNotFoundException
from corehq.apps.app_manager.templatetags.xforms_extras import translate
from corehq.apps.app_manager.util import (
    app_callout_templates,
    is_linked_app,
    is_usercase_in_use,
    module_loads_registry_case,
)
from corehq.apps.app_manager.views.apps import get_apps_base_context
from corehq.apps.app_manager.views.forms import FormHasSubmissionsView
from corehq.apps.app_manager.views.utils import (
    back_to_main,
    bail,
    form_has_submissions,
    set_lang_cookie,
)
from corehq.apps.cloudcare.utils import should_show_preview_app
from corehq.apps.domain.decorators import track_domain_request
from corehq.apps.fixtures.fixturegenerators import item_lists_by_domain
from corehq.apps.users.permissions import SUBMISSION_HISTORY_PERMISSION, has_permission_to_view_report
from corehq.util.view_utils import reverse as reverse_with_params

logger = logging.getLogger(__name__)


@require_can_edit_apps
@track_domain_request(calculated_prop='cp_n_form_builder_entered')
def form_source(request, domain, app_id, form_unique_id):
    app = get_app(domain, app_id)

    try:
        form = app.get_form(form_unique_id)
    except FormNotFoundException:
        return bail(request, domain, app_id, not_found="form")

    try:
        module = form.get_module()
    except AttributeError:
        return bail(request, domain, app_id, not_found="module")

    return _get_form_designer_view(request, domain, app, module, form)


@require_can_edit_apps
def form_source_legacy(request, domain, app_id, module_id=None, form_id=None):
    """
    This view has been kept around to not break any documentation on example apps
    and partner-distributed documentation on existing apps.
    PLEASE DO NOT DELETE.
    """
    app = get_app(domain, app_id)

    try:
        module = app.get_module(module_id)
    except ModuleNotFoundException:
        return bail(request, domain, app_id, not_found="module")

    try:
        form = module.get_form(form_id)
    except IndexError:
        return bail(request, domain, app_id, not_found="form")

    return _get_form_designer_view(request, domain, app, module, form)


def get_form_submit_history_url_for_last_30_days(request, domain, app, module, form):
    if not has_permission_to_view_report(request.couch_user, domain, SUBMISSION_HISTORY_PERMISSION):
        return None

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    params = {
        'form_status': 'active',
        'form_app_id': app.id if app else '',
        'form_module': module.id if module else '',
        'form_xmlns': form.xmlns if form and form.xmlns else '',
        'startdate': start_date.strftime('%Y-%m-%d'),
        'enddate': end_date.strftime('%Y-%m-%d'),
    }

    return reverse_with_params('project_report_dispatcher', args=[domain, 'submit_history'], params=params)


def _get_form_designer_view(request, domain, app, module, form):
    if app and app.copy_of:
        messages.warning(request, _(
            "You tried to edit a form that was from a previous release, so "
            "we have directed you to the latest version of your application."
        ))
        return back_to_main(request, domain, app_id=app.id)

    if not form.can_edit_in_vellum:
        messages.warning(request, _(
            "You tried to edit this form in the Form Builder. "
            "However, your administrator has locked this form against editing "
            "in the form builder, so we have redirected you to "
            "the form's front page instead."
        ))
        return back_to_main(request, domain, app_id=app.id,
                            form_unique_id=form.unique_id)

    if is_linked_app(app):
        messages.warning(request, _(
            "You tried to edit this form in the Form Builder. "
            "However, this is a linked application and you can only make changes to the "
            "upstream version."
        ))
        return back_to_main(request, domain, app_id=app.id)

    send_hubspot_form(HUBSPOT_FORM_BUILDER_FORM_ID, request)

    context = get_apps_base_context(request, domain, app)
    context.update(locals())

    vellum_options = _get_base_vellum_options(request, domain, form, context['lang'])
    vellum_options['core'] = _get_vellum_core_context(request, domain, app, module, form, context['lang'])
    vellum_options['plugins'] = _get_vellum_plugins(domain, form, module)
    vellum_options['features'] = _get_vellum_features(request, domain, app)
    context['vellum_options'] = vellum_options

    ckeditor_basepath = "formdesigner" if settings.VELLUM_DEBUG else "app_manager/js/vellum"
    ckeditor_basepath += "/lib/ckeditor/"

    context.update({
        'vellum_debug': settings.VELLUM_DEBUG,
        'nav_form': form,
        'formdesigner': True,

        'CKEDITOR_BASEPATH': ckeditor_basepath,
        'show_live_preview': should_show_preview_app(
            request,
            app,
            request.couch_user.username,
        ),
        'form_submit_history_url': get_form_submit_history_url_for_last_30_days(
            request,
            domain,
            app,
            module,
            form,
        ),
    })

    response = render(request, "app_manager/form_designer.html", context)
    set_lang_cookie(response, context['lang'])
    return response


@require_GET
@require_can_edit_apps
def get_form_data_schema(request, domain, app_id, form_unique_id):
    """Get data schema

    :returns: A list of data source schema definitions. A data source schema
    definition is a dictionary. For details on the content of the dictionary,
    see https://github.com/dimagi/Vellum/blob/master/src/datasources.js
    """
    data = []

    app = get_app(domain, app_id)
    form = app.get_form(form_unique_id)

    try:
        data.append(get_session_schema(form))
        if form.requires_case() or is_usercase_in_use(domain):
            data.append(get_casedb_schema(form))
        if form.requires_case() and module_loads_registry_case(form.get_module()):
            data.append(get_registry_schema(form))
    except AppManagerException as e:
        notify_exception(request, message=str(e))
        return HttpResponseBadRequest(
            str(e) or _("There is an error in the case management of your application. "
            "Please fix the error to see case properties in this tree")
        )
    except Exception as e:
        notify_exception(request, message=str(e))
        return HttpResponseBadRequest("schema error, see log for details")

    data.extend(item_lists_by_domain(domain))
    kw = {}
    if "pretty" in request.GET:
        kw["indent"] = 2
    return HttpResponse(json.dumps(data, **kw), content_type='application/json')


@require_GET
def ping(request):
    return HttpResponse("pong")


def _get_base_vellum_options(request, domain, form, displayLang):
    """
    Returns the base set of options that will be passed into Vellum
    when it is initialized.
    :param displayLang: --> derived from the base context
    """
    app = form.get_app()
    return {
        'intents': {
            'templates': next(app_callout_templates),
        },
        'javaRosa': {
            'langs': app.langs,
            'displayLanguage': displayLang,
            'showOnlyCurrentLang': (app.smart_lang_display and (len(app.langs) > 2)),
        },
        'uploader': {
            'uploadUrls': {
                'image': reverse("hqmedia_uploader_image", args=[domain, app.id]),
                'audio': reverse("hqmedia_uploader_audio", args=[domain, app.id]),
                'video': reverse("hqmedia_uploader_video", args=[domain, app.id]),
                'text': reverse("hqmedia_uploader_text", args=[domain, app.id]),
            },
            'objectMap': app.get_object_map(multimedia_map=form.get_relevant_multimedia_map(app)),
        },
    }


def _get_vellum_core_context(request, domain, app, module, form, lang):
    """
    Returns the core context that will be passed into vellum when it is
    initialized.
    """
    core = {
        'dataSourcesEndpoint': reverse('get_form_data_schema',
                                       kwargs={'domain': domain,
                                               'app_id': app.id,
                                               'form_unique_id': form.get_unique_id()}),
        'form': form.source,
        'formId': form.get_unique_id(),
        'formName': translate(form.name, app.langs[0], app.langs),
        'saveType': 'patch',
        'saveUrl': reverse('edit_form_attr',
                           args=[domain, app.id, form.get_unique_id(),
                                 'xform']),
        'patchUrl': reverse('patch_xform',
                            args=[domain, app.id, form.get_unique_id()]),
        'hasSubmissions': form_has_submissions(domain, app.id, form.get_unique_id()),
        'hasSubmissionsUrl': reverse(FormHasSubmissionsView.urlname,
                                     args=[domain, app.id, form.get_unique_id()]),
        'allowedDataNodeReferences': [
            "meta/deviceID",
            "meta/instanceID",
            "meta/username",
            "meta/userID",
            "meta/timeStart",
            "meta/timeEnd",
            "meta/location",
        ] + _get_core_context_scheduler_data_nodes(module, form),
        'activityUrl': reverse('ping'),
        'externalLinks': {
            'changeSubscription': reverse("domain_subscription_view",
                                          kwargs={'domain': domain}),
        },
        'invalidCaseProperties': ['name'],
    }
    core.update(_get_core_context_help_text_context(form))
    return core


def _get_vellum_plugins(domain, form, module):
    """
    Returns a list of enabled vellum plugins based on the domain's
    privileges.
    """
    vellum_plugins = ["modeliteration", "itemset", "atwho"]
    if (toggles.COMMTRACK.enabled(domain)
            or toggles.NON_COMMTRACK_LEDGERS.enabled(domain)):
        vellum_plugins.append("commtrack")
    if toggles.VELLUM_SAVE_TO_CASE.enabled(domain):
        vellum_plugins.append("saveToCase")
    if toggles.COMMCARE_CONNECT.enabled(domain):
        vellum_plugins.append("commcareConnect")

    form_uses_case = (
        (module and module.case_type and form.requires_case())
        or is_usercase_in_use(domain)
    )
    form_is_basic = form.doc_type == 'Form'
    if form_uses_case and form_is_basic:
        vellum_plugins.append("databrowser")

    return vellum_plugins


def _get_vellum_features(request, domain, app):
    """
    Returns the context of features passed into vellum when it is initialized.
    """
    vellum_features = toggles.toggles_dict(username=request.user.username,
                                           domain=domain)
    vellum_features.update({
        'group_in_field_list': app.enable_group_in_field_list,
        'image_resize': app.enable_image_resize,
        'markdown_in_groups': app.enable_markdown_in_groups,
        'lookup_tables': domain_has_privilege(domain, privileges.LOOKUP_TABLES),
        'templated_intents': domain_has_privilege(domain,
                                                  privileges.TEMPLATED_INTENTS),
        'custom_intents': domain_has_privilege(domain,
                                               privileges.CUSTOM_INTENTS),
        'rich_text': True,
        'sorted_itemsets': app.enable_sorted_itemsets,
        'advanced_itemsets': add_ons.show("advanced_itemsets", request, app),
        'markdown_tables': app.enable_markdown_tables,
        'use_custom_repeat_button_text': app.build_version >= LooseVersion('2.55'),
        'support_document_upload': app.support_document_upload,
    })
    return vellum_features


def _get_core_context_help_text_context(form):
    """
    Part of the vellum core context.

    Returns the appropriate icon context for the form type and the
    knockout template ID context for the correct help text
    information when opening a blank form with this type.
    """
    if form.get_action_type() == 'open':
        default_help_text_template_id = '#fd-hq-helptext-registration'
        form_icon_class = 'fcc fcc-app-createform'
    elif form.get_action_type() == 'close':
        default_help_text_template_id = '#fd-hq-helptext-close'
        form_icon_class = 'fcc fcc-app-completeform'
    elif form.get_action_type() == 'update':
        default_help_text_template_id = '#fd-hq-helptext-followup'
        form_icon_class = 'fcc fcc-app-updateform'
    else:
        default_help_text_template_id = '#fd-hq-helptext-survey'
        form_icon_class = 'fa-regular fa-file'
    return {
        'defaultHelpTextTemplateId': default_help_text_template_id,
        'formIconClass': form_icon_class,
    }


def _get_core_context_scheduler_data_nodes(module, form):
    """
    Part of the vellum core context.

    Returns a list of enabled scheduler data nodes.
    """
    has_schedule = (
        getattr(module, 'has_schedule', False)
        and getattr(form, 'schedule', False) and form.schedule.enabled
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
            "next_{}".format(f.schedule_form_id)
            for f in form.get_phase().get_forms()
            if getattr(f, 'schedule', False) and f.schedule.enabled
        ])
    return scheduler_data_nodes
