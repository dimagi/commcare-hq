from StringIO import StringIO
import copy
import logging
import hashlib
import itertools
from djangular.views.mixins import allow_remote_invocation, JSONResponseMixin
from lxml import etree
import os
import re
import json
from collections import defaultdict, OrderedDict
from xml.dom.minidom import parseString

from diff_match_patch import diff_match_patch
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _, get_language, ugettext_noop
from django.views.decorators.cache import cache_control
from corehq import ApplicationsTab, toggles, privileges, feature_previews
from corehq.apps.app_manager import commcare_settings
from corehq.apps.app_manager.exceptions import (
    AppEditingError,
    AppManagerException,
    BlankXFormError,
    ConflictingCaseTypeError,
    FormNotFoundException,
    IncompatibleFormTypeException,
    ModuleNotFoundException,
    RearrangeError,
)

from corehq.apps.app_manager.forms import CopyApplicationForm
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.translations import (
    expected_bulk_app_sheet_headers,
    process_bulk_app_translation_upload,
    expected_bulk_app_sheet_rows)
from corehq.apps.app_manager.view_helpers import ApplicationViewMixin
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.programs.models import Program
from corehq.apps.hqmedia.controller import (
    MultimediaImageUploadController,
    MultimediaAudioUploadController,
)
from corehq.apps.hqmedia.models import (
    ApplicationMediaReference,
    CommCareImage,
)
from corehq.apps.hqmedia.views import (
    DownloadMultimediaZip,
    ProcessImageFileUploadView,
    ProcessAudioFileUploadView,
)
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.reports.formdetails.readable import (
    FormQuestionResponse,
    questions_in_hierarchy,
)
from corehq.apps.sms.views import get_sms_autocomplete_context
from django.utils.http import urlencode as django_urlencode
from couchdbkit.exceptions import ResourceConflict
from django.http import HttpResponse, Http404, HttpResponseBadRequest, HttpResponseForbidden
from unidecode import unidecode
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse, RegexURLResolver, Resolver404
from django.shortcuts import render
from corehq.apps.translations import system_text_sources
from corehq.apps.translations.models import Translation
from corehq.util.view_utils import set_file_download
from dimagi.utils.django.cached_object import CachedObject
from django.utils.http import urlencode
from django.views.decorators.http import require_GET
from django.conf import settings
from couchdbkit.resource import ResourceNotFound
from corehq.apps.app_manager import app_strings
from corehq.apps.app_manager.const import (
    APP_V1,
    APP_V2,
    CAREPLAN_GOAL,
    CAREPLAN_TASK,
    MAJOR_RELEASE_TO_VERSION,
)
from corehq.apps.app_manager.success_message import SuccessMessage
from corehq.apps.app_manager.util import is_valid_case_type, get_all_case_properties, add_odk_profile_after_build, ParentCasePropertyBuilder, commtrack_ledger_sections
from corehq.apps.app_manager.util import save_xform, get_settings_values
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views import LoginAndDomainMixin
from corehq.util.compression import decompress
from couchexport.export import FormattedRow, export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from couchexport.writers import Excel2007ExportWriter
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.resource_conflict import retry_resource
from corehq.apps.app_manager.xform import (
    CaseError,
    XForm,
    XFormException,
    XFormValidationError,
    VELLUM_TYPES)
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.decorators.view import get_file
from dimagi.utils.django.cache import make_template_fragment_key
from dimagi.utils.excel import WorkbookJSONReader
from dimagi.utils.logging import notify_exception
from dimagi.utils.subprocess_timeout import ProcessTimedOut
from dimagi.utils.web import json_response, json_request
from corehq.apps.reports import util as report_utils
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.app_manager.models import (
    AdvancedForm,
    AdvancedFormActions,
    AdvancedModule,
    AppEditingError,
    Application,
    ApplicationBase,
    CareplanForm,
    CareplanModule,
    DeleteApplicationRecord,
    DeleteFormRecord,
    DeleteModuleRecord,
    DetailColumn,
    Form,
    FormActions,
    FormLink,
    FormNotFoundException,
    FormSchedule,
    IncompatibleFormTypeException,
    Module,
    ModuleNotFoundException,
    ParentSelect,
    SavedAppBuild,
    get_app,
    load_case_reserved_words,
    str_to_cls,
    DetailTab,
    ANDROID_LOGO_PROPERTY_MAPPING,
)
from corehq.apps.app_manager.models import import_app as import_app_util, SortElement
from dimagi.utils.web import get_url_base
from corehq.apps.app_manager.decorators import safe_download, no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps
from django.contrib import messages
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import ensure_request_has_privilege, has_privilege
# Numbers in paths is prohibited, hence the use of importlib
import importlib
FilterMigration = importlib.import_module('corehq.apps.app_manager.migrations.0002_add_filter_to_Detail').Migration

logger = logging.getLogger(__name__)


def _encode_if_unicode(s):
    return s.encode('utf-8') if isinstance(s, unicode) else s

CASE_TYPE_CONFLICT_MSG = (
    "Warning: The form's new module "
    "has a different case type from the old module.<br />"
    "Make sure all case properties you are loading "
    "are available in the new case type"
)


@require_deploy_apps
def back_to_main(req, domain, app_id=None, module_id=None, form_id=None,
                 unique_form_id=None, edit=True):
    """
    returns an HttpResponseRedirect back to the main page for the App Manager app
    with the correct GET parameters.

    This is meant to be used by views that process a POST request,
    which then redirect to the main page.

    """

    page = None
    params = {}
    if edit:
        params['edit'] = 'true'

    args = [domain]

    if app_id is not None:
        args.append(app_id)
        if unique_form_id is not None:
            app = get_app(domain, app_id)
            obj = app.get_form(unique_form_id, bare=False)
            if obj['type'] == 'user_registration':
                page = 'view_user_registration'
            else:
                module_id = obj['module'].id
                form_id = obj['form'].id
        if module_id is not None:
            args.append(module_id)
            if form_id is not None:
                args.append(form_id)


    if page:
        view_name = page
    else:
        view_name = {
            1: 'default',
            2: 'view_app',
            3: 'view_module',
            4: 'view_form',
            }[len(args)]

    return HttpResponseRedirect("%s%s" % (
        reverse('corehq.apps.app_manager.views.%s' % view_name, args=args),
        "?%s" % urlencode(params) if params else ""
        ))

def bail(req, domain, app_id, not_found=""):
    if not_found:
        messages.error(req, 'Oops! We could not find that %s. Please try again' % not_found)
    else:
        messages.error(req, 'Oops! We could not complete your request. Please try again')
    return back_to_main(req, domain, app_id)

def _get_xform_source(request, app, form, filename="form.xml"):
    download = json.loads(request.GET.get('download', 'false'))
    lang = request.COOKIES.get('lang', app.langs[0])
    source = form.source
    if download:
        response = HttpResponse(source)
        response['Content-Type'] = "application/xml"
        for lc in [lang] + app.langs:
            if lc in form.name:
                filename = "%s.xml" % unidecode(form.name[lc])
                break
        set_file_download(response, filename)
        return response
    else:
        return json_response(source)


@require_can_edit_apps
def get_xform_source(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    try:
        form = app.get_module(module_id).get_form(form_id)
    except IndexError:
        raise Http404()
    return _get_xform_source(req, app, form)


@require_can_edit_apps
def get_user_registration_source(req, domain, app_id):
    app = get_app(domain, app_id)
    form = app.get_user_registration()
    return _get_xform_source(req, app, form, filename="User Registration.xml")


def xform_display(req, domain, form_unique_id):
    try:
        form, app = Form.get_form(form_unique_id, and_app=True)
    except ResourceNotFound:
        raise Http404()
    if domain != app.domain:
        raise Http404()
    langs = [req.GET.get('lang')] + app.langs

    questions = form.get_questions(langs, include_triggers=True,
                                   include_groups=True)

    if req.GET.get('format') == 'html':
        questions = [FormQuestionResponse(q) for q in questions]

        return render(req, 'app_manager/xform_display.html', {
            'questions': questions_in_hierarchy(questions)
        })
    else:
        return json_response(questions)


@require_can_edit_apps
def form_casexml(req, domain, form_unique_id):
    try:
        form, app = Form.get_form(form_unique_id, and_app=True)
    except ResourceNotFound:
        raise Http404()
    if domain != app.domain:
        raise Http404()
    return HttpResponse(form.create_casexml())

@login_or_digest
@require_can_edit_apps
def app_source(req, domain, app_id):
    app = get_app(domain, app_id)
    return HttpResponse(app.export_json())


@require_can_edit_apps
def copy_app_check_domain(req, domain, name, app_id):
    app_copy = import_app_util(app_id, domain, name=name)
    return back_to_main(req, app_copy.domain, app_id=app_copy._id)


@require_can_edit_apps
def copy_app(req, domain):
    app_id = req.POST.get('app')
    form = CopyApplicationForm(app_id, req.POST)
    if form.is_valid():
        return copy_app_check_domain(req, form.cleaned_data['domain'], form.cleaned_data['name'], app_id)
    else:
        return view_generic(req, domain, app_id=app_id, copy_app_form=form)


@require_can_edit_apps
def migrate_app_filters(req, domain, app_id):
    message = "Migration succeeded!"
    try:
        app = get_app(domain, app_id)
        FilterMigration.migrate_app(app)
        app.save()
    except:
        message = "Migration failed :("
    return HttpResponse(message, content_type='text/plain')


@require_can_edit_apps
def import_app(req, domain, template="app_manager/import_app.html"):
    if req.method == "POST":
        _clear_app_cache(req, domain)
        name = req.POST.get('name')
        compressed = req.POST.get('compressed')

        valid_request = True
        if not name:
            messages.error(req, _("You must submit a name for the application you are importing."))
            valid_request = False
        if not compressed:
            messages.error(req, _("You must submit the source data."))
            valid_request = False

        if not valid_request:
            return render(req, template, {'domain': domain})

        source = decompress([chr(int(x)) if int(x) < 256 else int(x) for x in compressed.split(',')])
        source = json.loads(source)
        assert(source is not None)
        app = import_app_util(source, domain, name=name)

        return back_to_main(req, domain, app_id=app._id)
    else:
        app_id = req.GET.get('app')
        redirect_domain = req.GET.get('domain') or None
        if redirect_domain is not None:
            redirect_domain = redirect_domain.lower()
            if Domain.get_by_name(redirect_domain):
                return HttpResponseRedirect(
                    reverse('import_app', args=[redirect_domain])
                    + "?app={app_id}".format(app_id=app_id)
                )
            else:
                if redirect_domain:
                    messages.error(req, "We can't find a project called %s." % redirect_domain)
                else:
                    messages.error(req, "You left the project name blank.")
                return HttpResponseRedirect(req.META.get('HTTP_REFERER', req.path))

        if app_id:
            app = get_app(None, app_id)
            assert(app.get_doc_type() in ('Application', 'RemoteApp'))
            assert(req.couch_user.is_member_of(app.domain))
        else:
            app = None

        return render(req, template, {
            'domain': domain,
            'app': app,
            'is_superuser': req.couch_user.is_superuser
        })


@require_deploy_apps
def default(req, domain):
    """
    Handles a url that does not include an app_id.
    Currently the logic is taken care of by view_app,
    but this view exists so that there's something to
    reverse() to. (I guess I should use url(..., name="default")
    in url.py instead?)
    """
    return view_app(req, domain)


def get_form_view_context_and_template(request, form, langs, is_user_registration, messages=messages):
    xform_questions = []
    xform = None
    form_errors = []
    xform_validation_errored = False

    try:
        xform = form.wrapped_xform()
    except XFormException as e:
        form_errors.append(u"Error in form: %s" % e)
    except Exception as e:
        logging.exception(e)
        form_errors.append(u"Unexpected error in form: %s" % e)

    if xform and xform.exists():
        if xform.already_has_meta():
            messages.warning(request,
                "This form has a meta block already! "
                "It may be replaced by CommCare HQ's standard meta block."
            )

        try:
            form.validate_form()
            xform_questions = xform.get_questions(langs, include_triggers=True)
        except etree.XMLSyntaxError as e:
            form_errors.append(u"Syntax Error: %s" % e)
        except AppEditingError as e:
            form_errors.append(u"Error in application: %s" % e)
        except XFormValidationError:
            xform_validation_errored = True
            # showing these messages is handled by validate_form_for_build ajax
            pass
        except XFormException as e:
            form_errors.append(u"Error in form: %s" % e)
        # any other kind of error should fail hard,
        # but for now there are too many for that to be practical
        except Exception as e:
            if settings.DEBUG:
                raise
            notify_exception(request, 'Unexpected Build Error')
            form_errors.append(u"Unexpected System Error: %s" % e)
        else:
            # remove upload questions (attachemnts) until MM Case Properties
            # are released to general public
            is_previewer = toggles.MM_CASE_PROPERTIES.enabled(request.user.username)
            xform_questions = [q for q in xform_questions
                               if q["tag"] != "upload" or is_previewer]

        try:
            form_action_errors = form.validate_for_build()
            if not form_action_errors:
                form.add_stuff_to_xform(xform)
                if settings.DEBUG and False:
                    xform.validate()
        except CaseError as e:
            messages.error(request, u"Error in Case Management: %s" % e)
        except XFormValidationError as e:
            messages.error(request, unicode(e))
        except Exception as e:
            if settings.DEBUG:
                raise
            logging.exception(unicode(e))
            messages.error(request, u"Unexpected Error: %s" % e)

    try:
        languages = xform.get_languages()
    except Exception:
        languages = []

    for err in form_errors:
        messages.error(request, err)

    module_case_types = []
    app = form.get_app()
    if is_user_registration:
        module_case_types = None
    else:
        for module in app.get_modules():
            for case_type in module.get_case_types():
                module_case_types.append({
                    'id': module.unique_id,
                    'module_name': trans(module.name, langs),
                    'case_type': case_type,
                    'module_type': module.doc_type
                })

    if not form.unique_id:
        form.get_unique_id()
        app.save()

    context = {
        'is_user_registration': is_user_registration,
        'nav_form': form if not is_user_registration else '',
        'xform_languages': languages,
        "xform_questions": xform_questions,
        'case_reserved_words_json': load_case_reserved_words(),
        'module_case_types': module_case_types,
        'form_errors': form_errors,
        'xform_validation_errored': xform_validation_errored,
        'allow_cloudcare': app.application_version == APP_V2 and isinstance(form, Form),
        'allow_form_copy': isinstance(form, Form),
        'allow_form_filtering': not isinstance(form, CareplanForm),
        'allow_form_workflow': not isinstance(form, CareplanForm),
    }

    if isinstance(form, CareplanForm):
        context.update({
            'mode': form.mode,
            'fixed_questions': form.get_fixed_questions(),
            'custom_case_properties': [{'key': key, 'path': path} for key, path in form.custom_case_updates.items()],
            'case_preload': [{'key': key, 'path': path} for key, path in form.case_preload.items()],
        })
        return "app_manager/form_view_careplan.html", context
    elif isinstance(form, AdvancedForm):
        def commtrack_programs():
            if app.commtrack_enabled:
                programs = Program.by_domain(app.domain)
                return [{'value': program.get_id, 'label': program.name} for program in programs]
            else:
                return []

        all_programs = [{'value': '', 'label': _('All Programs')}]
        context.update({
            'show_custom_ref': toggles.APP_BUILDER_CUSTOM_PARENT_REF.enabled(request.user.username),
            'commtrack_programs': all_programs + commtrack_programs(),
        })
        return "app_manager/form_view_advanced.html", context
    else:
        context.update({
            'show_custom_ref': toggles.APP_BUILDER_CUSTOM_PARENT_REF.enabled(request.user.username),
        })
        return "app_manager/form_view.html", context


def get_app_view_context(request, app):

    is_cloudcare_allowed = has_privilege(request, privileges.CLOUDCARE)

    settings_layout = copy.deepcopy(
        commcare_settings.LAYOUT[app.get_doc_type()])
    for section in settings_layout:
        new_settings = []
        for setting in section['settings']:
            toggle_name = setting.get('toggle')
            if toggle_name and not toggle_enabled(request, toggle_name):
                continue
            privilege_name = setting.get('privilege')
            if privilege_name and not has_privilege(request, privilege_name):
                continue
            new_settings.append(setting)
        section['settings'] = new_settings

    context = {
        'settings_layout': settings_layout,
        'settings_values': get_settings_values(app),
        'is_cloudcare_allowed': is_cloudcare_allowed,
    }

    build_config = CommCareBuildConfig.fetch()
    options = build_config.get_menu()
    if not request.user.is_superuser:
        options = [option for option in options if not option.superuser_only]
    options_map = defaultdict(lambda:{"values": [], "value_names": []})
    for option in options:
        builds = options_map[option.build.major_release()]
        builds["values"].append(option.build.to_string())
        builds["value_names"].append(option.get_label())
        if "default" not in builds:
            app_ver = MAJOR_RELEASE_TO_VERSION[option.build.major_release()]
            builds["default"] = build_config.get_default(app_ver).to_string()

    (build_spec_setting,) = filter(
        lambda x: x['type'] == 'hq' and x['id'] == 'build_spec',
        [setting for section in context['settings_layout']
            for setting in section['settings']]
    )
    build_spec_setting['options_map'] = options_map
    build_spec_setting['default_app_version'] = app.application_version

    context.update({
        'bulk_ui_translation_upload': {
            'action': reverse('upload_bulk_ui_translations',
                              args=(app.domain, app.get_id)),
            'download_url': reverse('download_bulk_ui_translations',
                                    args=(app.domain, app.get_id)),
            'adjective': _(u"U\u200BI translation"),
            'plural_noun': _(u"U\u200BI translations"),
        },
        'bulk_app_translation_upload': {
            'action': reverse('upload_bulk_app_translations',
                              args=(app.domain, app.get_id)),
            'download_url': reverse('download_bulk_app_translations',
                                    args=(app.domain, app.get_id)),
            'adjective': _("app translation"),
            'plural_noun': _("app translations"),
        },
    })
    context.update({
        'bulk_ui_translation_form': get_bulk_upload_form(
            context,
            context_key="bulk_ui_translation_upload"
        ),
        'bulk_app_translation_form': get_bulk_upload_form(
            context,
            context_key="bulk_app_translation_upload"
        )
    })
    return context


def get_langs(request, app):
    lang = request.GET.get('lang',
        request.COOKIES.get('lang', app.langs[0] if hasattr(app, 'langs') and app.langs else '')
    )
    langs = None
    if app and hasattr(app, 'langs'):
        if not app.langs and not app.is_remote_app:
            # lots of things fail if the app doesn't have any languages.
            # the best we can do is add 'en' if there's nothing else.
            app.langs.append('en')
            app.save()
        if not lang or lang not in app.langs:
            lang = (app.langs or ['en'])[0]
        langs = [lang] + app.langs
    return lang, langs


def _clear_app_cache(request, domain):
    from corehq import ApplicationsTab
    ApplicationBase.get_db().view('app_manager/applications_brief',
        startkey=[domain],
        limit=1,
    ).all()
    for is_active in True, False:
        key = make_template_fragment_key('header_tab', [
            domain,
            None, # tab.org should be None for any non org page
            ApplicationsTab.view,
            is_active,
            request.couch_user.get_id,
            get_language(),
        ])
        cache.delete(key)


def _get_edit(request, domain):
    if getattr(request, 'couch_user', None):
        return (
            (request.GET.get('edit', 'true') == 'true') and
            (request.couch_user.can_edit_apps(domain) or request.user.is_superuser)
        )
    else:
        return False


def get_apps_base_context(request, domain, app):

    lang, langs = get_langs(request, app)

    edit = _get_edit(request, domain)

    if getattr(request, 'couch_user', None):
        timezone = report_utils.get_timezone(request.couch_user, domain)
    else:
        timezone = None

    context = {
        'lang': lang,
        'langs': langs,
        'domain': domain,
        'edit': edit,
        'app': app,
        'URL_BASE': get_url_base(),
        'timezone': timezone,
    }

    if app:
        for _lang in app.langs:
            try:
                SuccessMessage(app.success_message.get(_lang, ''), '').check_message()
            except Exception as e:
                messages.error(request, "Your success message is malformed: %s is not a keyword" % e)

        v2_app = app.application_version == APP_V2
        context.update({
            'show_care_plan': (v2_app
                               and not app.has_careplan_module
                               and toggles.APP_BUILDER_CAREPLAN.enabled(request.user.username)),
            'show_advanced': (v2_app
                               and (toggles.APP_BUILDER_ADVANCED.enabled(request.user.username)
                                    or getattr(app, 'commtrack_enabled', False))),
        })

    return context


@cache_control(no_cache=True, no_store=True)
@require_deploy_apps
def paginate_releases(request, domain, app_id):
    limit = request.GET.get('limit')
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    start_build_param = request.GET.get('start_build')
    if start_build_param and json.loads(start_build_param):
        start_build = json.loads(start_build_param)
        assert isinstance(start_build, int)
    else:
        start_build = {}
    timezone = report_utils.get_timezone(request.couch_user, domain)
    saved_apps = get_db().view('app_manager/saved_app',
        startkey=[domain, app_id, start_build],
        endkey=[domain, app_id],
        descending=True,
        limit=limit,
        wrapper=lambda x: SavedAppBuild.wrap(x['value']).to_saved_build_json(timezone),
    ).all()
    include_media = toggles.APP_BUILDER_INCLUDE_MULTIMEDIA_ODK.enabled(
        request.user.username
    )
    for app in saved_apps:
        app['include_media'] = include_media and app['doc_type'] != 'RemoteApp'
    return json_response(saved_apps)


@require_deploy_apps
def release_manager(request, domain, app_id, template='app_manager/releases.html'):
    app = get_app(domain, app_id)
    context = get_apps_base_context(request, domain, app)
    context['sms_contacts'] = get_sms_autocomplete_context(request, domain)['sms_contacts']

    context.update({
        'release_manager': True,
    })
    if not app.is_remote_app():
        # Multimedia is not supported for remote applications at this time.
        # todo remove get_media_references
        multimedia = app.get_media_references()
        context.update({
            'multimedia': multimedia,
        })
    response = render(request, template, context)
    response.set_cookie('lang', _encode_if_unicode(context['lang']))
    return response


@login_and_domain_required
def current_app_version(request, domain, app_id):
    """
    Return current app version and the latest release
    """
    app = get_app(domain, app_id)
    latest = get_db().view('app_manager/saved_app',
        startkey=[domain, app_id, {}],
        endkey=[domain, app_id],
        descending=True,
        limit=1,
    ).first()
    latest_release = latest['value']['version'] if latest else None
    return json_response({
        'currentVersion': app.version,
        'latestRelease': latest_release,
    })


@no_conflict_require_POST
@require_can_edit_apps
def release_build(request, domain, app_id, saved_app_id):
    is_released = request.POST.get('is_released') == 'true'
    ajax = request.POST.get('ajax') == 'true'
    saved_app = get_app(domain, saved_app_id)
    if saved_app.copy_of != app_id:
        raise Http404
    saved_app.is_released = is_released
    saved_app.save(increment_version=False)
    from corehq.apps.app_manager.signals import app_post_release
    app_post_release.send(Application, application=saved_app)
    if ajax:
        return json_response({'is_released': is_released})
    else:
        return HttpResponseRedirect(reverse('release_manager', args=[domain, app_id]))


def get_module_view_context_and_template(app, module):
    defaults = ('name', 'date-opened', 'status')
    if app.case_sharing:
        defaults += ('#owner_name',)
    builder = ParentCasePropertyBuilder(app, defaults=defaults)
    child_case_types = set()
    for m in app.get_modules():
        if m.case_type == module.case_type:
            child_case_types.update(m.get_child_case_types())
    child_case_types = list(child_case_types)
    fixtures = [f.tag for f in FixtureDataType.by_domain(app.domain)]

    def ensure_unique_ids():
        # make sure all modules have unique ids
        modules = app.modules
        if any(not mod.unique_id for mod in modules):
            for mod in modules:
                mod.get_or_create_unique_id()
            app.save()

    def get_parent_modules(case_type):
        parent_types = builder.get_parent_types(case_type)
        modules = app.modules
        parent_module_ids = [mod.unique_id for mod in modules
                             if mod.case_type in parent_types]
        return [{
            'unique_id': mod.unique_id,
            'name': mod.name,
            'is_parent': mod.unique_id in parent_module_ids,
        } for mod in app.modules if mod.case_type != case_type and mod.unique_id != module.unique_id]

    def case_list_form_options(case_type):
        options = OrderedDict()
        forms = [
            form
            for mod in app.get_modules() if module.unique_id != mod.unique_id
            for form in mod.get_forms() if form.is_registration_form(case_type)
        ]
        if forms or module.case_list_form.form_id:
            options['disabled'] = _("Don't show")
            options.update({f.unique_id: trans(f.name, app.langs) for f in forms})

        if not options:
            options['disabled'] = _("No suitable forms available")

        return options

    ensure_unique_ids()
    if isinstance(module, CareplanModule):
        return "app_manager/module_view_careplan.html", {
            'parent_modules': get_parent_modules(CAREPLAN_GOAL),
            'fixtures': fixtures,
            'details': [
                {
                    'label': _('Goal List'),
                    'detail_label': _('Goal Detail'),
                    'type': 'careplan_goal',
                    'model': 'case',
                    'properties': sorted(builder.get_properties(CAREPLAN_GOAL)),
                    'sort_elements': module.goal_details.short.sort_elements,
                    'short': module.goal_details.short,
                    'long': module.goal_details.long,
                    'child_case_types': child_case_types,
                },
                {
                    'label': _('Task List'),
                    'detail_label': _('Task Detail'),
                    'type': 'careplan_task',
                    'model': 'case',
                    'properties': sorted(builder.get_properties(CAREPLAN_TASK)),
                    'sort_elements': module.task_details.short.sort_elements,
                    'short': module.task_details.short,
                    'long': module.task_details.long,
                    'child_case_types': child_case_types,
                },
            ],
        }
    elif isinstance(module, AdvancedModule):
        case_type = module.case_type
        def get_details():
            details = [{
                'label': _('Case List'),
                'detail_label': _('Case Detail'),
                'type': 'case',
                'model': 'case',
                'properties': sorted(builder.get_properties(case_type)),
                'sort_elements': module.case_details.short.sort_elements,
                'short': module.case_details.short,
                'long': module.case_details.long,
                'child_case_types': child_case_types,
            }]

            if app.commtrack_enabled:
                details.append({
                    'label': _('Product List'),
                    'detail_label': _('Product Detail'),
                    'type': 'product',
                    'model': 'product',
                    'properties': ['name'] + commtrack_ledger_sections(app.commtrack_requisition_mode),
                    'sort_elements': module.product_details.short.sort_elements,
                    'short': module.product_details.short,
                    'child_case_types': child_case_types,
                })

            return details

        return "app_manager/module_view_advanced.html", {
            'fixtures': fixtures,
            'details': get_details(),
            'case_list_form_options': case_list_form_options(case_type),
            'case_list_form_allowed': module.all_forms_require_a_case
        }
    else:
        case_type = module.case_type
        return "app_manager/module_view.html", {
            'parent_modules': get_parent_modules(case_type),
            'fixtures': fixtures,
            'details': [
                {
                    'label': _('Case List'),
                    'detail_label': _('Case Detail'),
                    'type': 'case',
                    'model': 'case',
                    'properties': sorted(builder.get_properties(case_type)),
                    'sort_elements': module.case_details.short.sort_elements,
                    'short': module.case_details.short,
                    'long': module.case_details.long,
                    'parent_select': module.parent_select,
                    'child_case_types': child_case_types,
                },
            ],
            'case_list_form_options': case_list_form_options(case_type),
            'case_list_form_allowed': module.all_forms_require_a_case and not module.parent_select.active
        }


@retry_resource(3)
def view_generic(req, domain, app_id=None, module_id=None, form_id=None, is_user_registration=False, copy_app_form=None):
    """
    This is the main view for the app. All other views redirect to here.

    """
    if form_id and not module_id:
        return bail(req, domain, app_id)

    app = module = form = None
    try:
        if app_id:
            app = get_app(domain, app_id)
        if is_user_registration:
            if not app.show_user_registration:
                raise Http404()
            form = app.get_user_registration()
        if module_id:
            try:
                module = app.get_module(module_id)
            except ModuleNotFoundException:
                raise Http404()
            if not module.unique_id:
                module.get_or_create_unique_id()
                app.save()
        if form_id:
            try:
                form = module.get_form(form_id)
            except IndexError:
                raise Http404()
    except ModuleNotFoundException:
        return bail(req, domain, app_id)

    context = get_apps_base_context(req, domain, app)
    if not app:
        all_applications = ApplicationBase.view('app_manager/applications_brief',
            startkey=[domain],
            endkey=[domain, {}],
            #stale=settings.COUCH_STALE_QUERY,
        ).all()
        if all_applications:
            app_id = all_applications[0].id
            return back_to_main(req, domain, app_id=app_id, module_id=module_id,
                                form_id=form_id)
    if app and app.copy_of:
        # don't fail hard.
        return HttpResponseRedirect(reverse("corehq.apps.app_manager.views.view_app", args=[domain,app.copy_of]))

    # grandfather in people who set commcare sense earlier
    if app and 'use_commcare_sense' in app:
        if app['use_commcare_sense']:
            if 'features' not in app.profile:
                app.profile['features'] = {}
            app.profile['features']['sense'] = 'true'
        del app['use_commcare_sense']
        app.save()

    context.update({
        'module': module,
        'form': form,
    })

    if app and not module and hasattr(app, 'translations'):
        context.update({"translations": app.translations.get(context['lang'], {})})

    if form:
        template, form_context = get_form_view_context_and_template(req, form, context['langs'], is_user_registration)
        context.update({
            'case_properties': get_all_case_properties(app),
        })

        if toggles.FORM_LINK_WORKFLOW.enabled(req.user.username):
            modules = filter(lambda m: m.case_type == module.case_type, app.get_modules())
            linkable_forms = list(itertools.chain.from_iterable(list(m.get_forms()) for m in modules))
            context.update({
                'linkable_forms': map(
                    lambda f: {'unique_id': f.unique_id, 'name': trans(f.name, app.langs)},
                    linkable_forms
                )
            })

        context.update(form_context)
    elif module:
        template, module_context = get_module_view_context_and_template(app, module)
        context.update(module_context)
    else:
        template = "app_manager/app_view.html"
        if app:
            context.update(get_app_view_context(req, app))

    # update multimedia context for forms and modules.
    menu_host = form or module
    if menu_host:

        default_file_name = 'module%s' % module_id
        if form_id:
            default_file_name = '%s_form%s' % (default_file_name, form_id)

        specific_media = {
            'menu': {
                'menu_refs': app.get_menu_media(
                    module, module_id, form=form, form_index=form_id
                ),
                'default_file_name': default_file_name,
            }
        }
        if module:
            specific_media['case_list_form'] = {
                'menu_refs': app.get_case_list_form_media(module, module_id),
                'default_file_name': '{}_case_list_form'.format(default_file_name),
            }
        context.update({
            'multimedia': {
                "references": app.get_references(),
                "object_map": app.get_object_map(),
                'upload_managers': {
                    'icon': MultimediaImageUploadController(
                        "hqimage",
                        reverse(ProcessImageFileUploadView.name,
                                args=[app.domain, app.get_id])
                    ),
                    'audio': MultimediaAudioUploadController(
                        "hqaudio", reverse(ProcessAudioFileUploadView.name,
                                args=[app.domain, app.get_id])
                    ),
                },
            }
        })
        context['multimedia'].update(specific_media)

    error = req.GET.get('error', '')

    context.update({
        'error':error,
        'app': app,
    })

    # Pass form for Copy Application to template:
    context.update({
        'copy_app_form': copy_app_form if copy_app_form is not None else CopyApplicationForm(app_id)
    })

    if app and app.doc_type == 'Application' and has_privilege(req, privileges.COMMCARE_LOGO_UPLOADER):
        uploader_slugs = ANDROID_LOGO_PROPERTY_MAPPING.keys()
        from corehq.apps.hqmedia.controller import MultimediaLogoUploadController
        from corehq.apps.hqmedia.views import ProcessLogoFileUploadView
        context.update({
            "sessionid": req.COOKIES.get('sessionid'),
            'uploaders': [
                MultimediaLogoUploadController(
                    slug,
                    reverse(
                        ProcessLogoFileUploadView.name,
                        args=[domain, app_id, slug],
                    )
                )
                for slug in uploader_slugs
            ],
            "refs": {
                slug: ApplicationMediaReference(
                    app.logo_refs.get(slug, {}).get("path", slug),
                    media_class=CommCareImage,
                    module_id=app.logo_refs.get(slug, {}).get("m_id"),
                ).as_dict()
                for slug in uploader_slugs
            },
            "media_info": {
                slug: app.logo_refs.get(slug)
                for slug in uploader_slugs if app.logo_refs.get(slug)
            },
        })

    response = render(req, template, context)
    response.set_cookie('lang', _encode_if_unicode(context['lang']))
    return response


@require_can_edit_apps
def get_commcare_version(request, app_id, app_version):
    options = CommCareBuildConfig.fetch().get_menu(app_version)
    return json_response(options)


@require_can_edit_apps
def view_user_registration(request, domain, app_id):
    return view_generic(request, domain, app_id, is_user_registration=True)


@require_GET
@require_deploy_apps
def view_form(req, domain, app_id, module_id, form_id):
    return view_generic(req, domain, app_id, module_id, form_id)


@require_GET
@require_deploy_apps
def view_module(req, domain, app_id, module_id):
    return view_generic(req, domain, app_id, module_id)


@require_GET
@require_deploy_apps
def view_app(req, domain, app_id=None):
    # redirect old m=&f= urls
    module_id = req.GET.get('m', None)
    form_id = req.GET.get('f', None)
    if module_id or form_id:
        return back_to_main(req, domain, app_id=app_id, module_id=module_id,
                            form_id=form_id)

    return view_generic(req, domain, app_id)


@require_deploy_apps
def multimedia_ajax(request, domain, app_id, template='app_manager/partials/multimedia_ajax.html'):
    app = get_app(domain, app_id)
    if app.get_doc_type() == 'Application':
        try:
            # todo remove get_media_references
            multimedia = app.get_media_references()
        except ProcessTimedOut:
            notify_exception(request)
            messages.warning(request, (
                "We were unable to check if your forms had errors. "
                "Refresh the page and we will try again."
            ))
            multimedia = {
                'references': {},
                'form_errors': True,
                'missing_refs': False,
            }
        context = {
            'multimedia': multimedia,
            'domain': domain,
            'app': app,
            'edit': _get_edit(request, domain)
        }
        return render(request, template, context)
    else:
        raise Http404()


@require_can_edit_apps
def form_source(req, domain, app_id, module_id, form_id):
    return form_designer(req, domain, app_id, module_id, form_id)


@require_can_edit_apps
def user_registration_source(req, domain, app_id):
    return form_designer(req, domain, app_id, is_user_registration=True)


@require_can_edit_apps
def form_designer(req, domain, app_id, module_id=None, form_id=None,
                  is_user_registration=False):
    app = get_app(domain, app_id)

    if is_user_registration:
        form = app.get_user_registration()
    else:
        try:
            module = app.get_module(module_id)
        except ModuleNotFoundException:
            return bail(req, domain, app_id, not_found="module")
        try:
            form = module.get_form(form_id)
        except IndexError:
            return bail(req, domain, app_id, not_found="form")

    if form.no_vellum:
        messages.warning(req, _(
            "You tried to edit this form in the Form Builder. "
            "However, your administrator has locked this form against editing "
            "in the form builder, so we have redirected you to "
            "the form's front page instead."
        ))
        return back_to_main(req, domain, app_id=app_id,
                            unique_form_id=form.unique_id)

    vellum_plugins = ["modeliteration"]
    if toggles.VELLUM_ITEMSETS.enabled(domain):
        vellum_plugins.append("itemset")
    if toggles.VELLUM_TRANSACTION_QUESTION_TYPES.enabled(domain):
        vellum_plugins.append("commtrack")

    vellum_features = toggles.toggles_dict(username=req.user.username,
                                           domain=domain)
    vellum_features.update({
        'group_in_field_list': app.enable_group_in_field_list
    })
    context = get_apps_base_context(req, domain, app)
    context.update(locals())
    context.update({
        'vellum_debug': settings.VELLUM_DEBUG,
        'edit': True,
        'nav_form': form if not is_user_registration else '',
        'formdesigner': True,
        'multimedia_object_map': app.get_object_map(),
        'sessionid': req.COOKIES.get('sessionid'),
        'features': vellum_features,
        'plugins': vellum_plugins,
    })
    return render(req, 'app_manager/form_designer.html', context)



@no_conflict_require_POST
@require_can_edit_apps
def new_app(req, domain):
    "Adds an app to the database"
    lang = 'en'
    type = req.POST["type"]
    application_version = req.POST.get('application_version', APP_V1)
    cls = str_to_cls[type]
    if cls == Application:
        app = cls.new_app(domain, "Untitled Application", lang=lang, application_version=application_version)
        app.add_module(Module.new_module("Untitled Module", lang))
        app.new_form(0, "Untitled Form", lang)
    else:
        app = cls.new_app(domain, "Untitled Application", lang=lang)
    if req.project.secure_submissions:
        app.secure_submissions = True
    app.save()
    _clear_app_cache(req, domain)
    app_id = app.id

    return back_to_main(req, domain, app_id=app_id)

@require_can_edit_apps
def default_new_app(req, domain):
    """New Blank Application according to defaults. So that we can link here
    instead of creating a form and posting to the above link, which was getting
    annoying for the Dashboard.
    """
    lang = 'en'
    app = Application.new_app(
        domain, _("Untitled Application"), lang=lang,
        application_version=APP_V2
    )
    app.add_module(Module.new_module(_("Untitled Module"), lang))
    app.new_form(0, "Untitled Form", lang)
    if req.project.secure_submissions:
        app.secure_submissions = True
    _clear_app_cache(req, domain)
    app.save()
    return back_to_main(req, domain, app_id=app.id)


@no_conflict_require_POST
@require_can_edit_apps
def new_module(req, domain, app_id):
    "Adds a module to an app"
    app = get_app(domain, app_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    name = req.POST.get('name')
    module_type = req.POST.get('module_type', 'case')
    if module_type == 'case':
        module = app.add_module(Module.new_module(name, lang))
        module_id = module.id
        app.new_form(module_id, "Untitled Form", lang)
        app.save()
        response = back_to_main(req, domain, app_id=app_id, module_id=module_id)
        response.set_cookie('suppress_build_errors', 'yes')
        return response
    elif module_type in MODULE_TYPE_MAP:
        fn = MODULE_TYPE_MAP[module_type][FN]
        validations = MODULE_TYPE_MAP[module_type][VALIDATIONS]
        error = next((v[1] for v in validations if v[0](app)), None)
        if error:
            messages.warning(req, error)
            return back_to_main(req, domain, app_id=app.id)
        else:
            return fn(req, domain, app, name, lang)
    else:
        logger.error('Unexpected module type for new module: "%s"' % module_type)
        return back_to_main(req, domain, app_id=app_id)


def _new_careplan_module(req, domain, app, name, lang):
    from corehq.apps.app_manager.util import new_careplan_module
    target_module_index = req.POST.get('target_module_id')
    target_module = app.get_module(target_module_index)
    if not target_module.case_type:
        name = target_module.name[lang]
        messages.error(req, _("Please set the case type for the target module '{name}'.".format(name=name)))
        return back_to_main(req, domain, app_id=app.id)
    module = new_careplan_module(app, name, lang, target_module)
    app.save()
    response = back_to_main(req, domain, app_id=app.id, module_id=module.id)
    response.set_cookie('suppress_build_errors', 'yes')
    messages.info(req, _('Caution: Care Plan modules are a labs feature'))
    return response


def _new_advanced_module(req, domain, app, name, lang):
    module = app.add_module(AdvancedModule.new_module(name, lang))
    module_id = module.id
    app.new_form(module_id, _("Untitled Form"), lang)

    app.save()
    response = back_to_main(req, domain, app_id=app.id, module_id=module_id)
    response.set_cookie('suppress_build_errors', 'yes')
    messages.info(req, _('Caution: Advanced modules are a labs feature'))
    return response


@no_conflict_require_POST
@require_can_edit_apps
def new_form(req, domain, app_id, module_id):
    "Adds a form to an app (under a module)"
    app = get_app(domain, app_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    name = req.POST.get('name')
    form = app.new_form(module_id, name, lang)
    app.save()
    # add form_id to locals()
    form_id = form.id
    response = back_to_main(req, domain, app_id=app_id, module_id=module_id,
                            form_id=form_id)
    return response

@no_conflict_require_POST
@require_can_edit_apps
def delete_app(req, domain, app_id):
    "Deletes an app from the database"
    app = get_app(domain, app_id)
    record = app.delete_app()
    messages.success(req,
        'You have deleted an application. <a href="%s" class="post-link">Undo</a>' % reverse('undo_delete_app', args=[domain, record.get_id]),
        extra_tags='html'
    )
    app.save()
    _clear_app_cache(req, domain)
    return back_to_main(req, domain)

@no_conflict_require_POST
@require_can_edit_apps
def undo_delete_app(request, domain, record_id):
    try:
        app = get_app(domain, record_id)
        app.unretire()
        app_id = app.id
    except Exception:
        record = DeleteApplicationRecord.get(record_id)
        record.undo()
        app_id = record.app_id
    _clear_app_cache(request, domain)
    messages.success(request, 'Application successfully restored.')
    return back_to_main(request, domain, app_id=app_id)

@no_conflict_require_POST
@require_can_edit_apps
def delete_module(req, domain, app_id, module_unique_id):
    "Deletes a module from an app"
    app = get_app(domain, app_id)
    try:
        record = app.delete_module(module_unique_id)
    except ModuleNotFoundException:
        return bail(req, domain, app_id)
    if record is not None:
        messages.success(req,
            'You have deleted a module. <a href="%s" class="post-link">Undo</a>' % reverse('undo_delete_module', args=[domain, record.get_id]),
            extra_tags='html'
        )
        app.save()
    return back_to_main(req, domain, app_id=app_id)

@no_conflict_require_POST
@require_can_edit_apps
def undo_delete_module(request, domain, record_id):
    record = DeleteModuleRecord.get(record_id)
    record.undo()
    messages.success(request, 'Module successfully restored.')
    return back_to_main(request, domain, app_id=record.app_id, module_id=record.module_id)


@no_conflict_require_POST
@require_can_edit_apps
def delete_form(req, domain, app_id, module_unique_id, form_unique_id):
    "Deletes a form from an app"
    app = get_app(domain, app_id)
    record = app.delete_form(module_unique_id, form_unique_id)
    if record is not None:
        messages.success(
            req,
            'You have deleted a form. <a href="%s" class="post-link">Undo</a>'
            % reverse('undo_delete_form', args=[domain, record.get_id]),
            extra_tags='html'
        )
        app.save()
    return back_to_main(
        req, domain, app_id=app_id,
        module_id=app.get_module_by_unique_id(module_unique_id).id)


@no_conflict_require_POST
@require_can_edit_apps
def copy_form(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    to_module_id = int(req.POST['to_module_id'])
    try:
        app.copy_form(int(module_id), int(form_id), to_module_id)
    except ConflictingCaseTypeError:
        messages.warning(req, CASE_TYPE_CONFLICT_MSG,  extra_tags="html")
        app.save()
    except BlankXFormError:
        # don't save!
        messages.error(req, _('We could not copy this form, because it is blank.'
                              'In order to copy this form, please add some questions first.'))
    except IncompatibleFormTypeException:
        # don't save!
        messages.error(req, _('This form could not be copied because it '
                              'is not compatible with the selected module.'))
    else:
        app.save()

    return back_to_main(req, domain, app_id=app_id, module_id=module_id,
                        form_id=form_id)


@no_conflict_require_POST
@require_can_edit_apps
def undo_delete_form(request, domain, record_id):
    record = DeleteFormRecord.get(record_id)
    try:
        record.undo()
        messages.success(request, 'Form successfully restored.')
    except ModuleNotFoundException:
        messages.error(request,
                       'Form could not be restored: module is missing.')

    return back_to_main(request, domain, app_id=record.app_id,
                        module_id=record.module_id, form_id=record.form_id)

@no_conflict_require_POST
@require_can_edit_apps
def edit_module_attr(req, domain, app_id, module_id, attr):
    """
    Called to edit any (supported) module attribute, given by attr
    """
    attributes = {
        "all": None,
        "case_type": None, "put_in_root": None, "display_separately": None,
        "name": None, "case_label": None, "referral_label": None,
        'media_image': None, 'media_audio': None, 'has_schedule': None,
        "case_list": ('case_list-show', 'case_list-label'),
        "task_list": ('task_list-show', 'task_list-label'),
        "case_list_form_id": None,
        "case_list_form_label": None,
        "case_list_form_media_image": None,
        "case_list_form_media_audio": None,
        "parent_module": None,
        "root_module_id": None,
    }

    if attr not in attributes:
        return HttpResponseBadRequest()

    def should_edit(attribute):
        if attribute == attr:
            return True
        if 'all' == attr:
            if attributes[attribute]:
                for param in attributes[attribute]:
                    if not req.POST.get(param):
                        return False
                return True
            else:
                return req.POST.get(attribute) is not None

    app = get_app(domain, app_id)
    module = app.get_module(module_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    resp = {'update': {}, 'corrections': {}}
    if should_edit("case_type"):
        case_type = req.POST.get("case_type", None)
        if is_valid_case_type(case_type):
            # todo: something better than nothing when invalid
            old_case_type = module["case_type"]
            module["case_type"] = case_type
            for cp_mod in (mod for mod in app.modules if isinstance(mod, CareplanModule)):
                if cp_mod.unique_id != module.unique_id and cp_mod.parent_select.module_id == module.unique_id:
                    cp_mod.case_type = case_type

            def rename_action_case_type(mod):
                for form in mod.forms:
                    for action in form.actions.get_all_actions():
                        if action.case_type == old_case_type:
                            action.case_type = case_type

            if isinstance(module, AdvancedModule):
                rename_action_case_type(module)
            for ad_mod in (mod for mod in app.modules if isinstance(mod, AdvancedModule)):
                if ad_mod.unique_id != module.unique_id and ad_mod.case_type != old_case_type:
                    # only apply change if the module's case_type does not reference the old value
                    rename_action_case_type(ad_mod)
        else:
            return HttpResponseBadRequest("case type is improperly formatted")
    if should_edit("put_in_root"):
        module["put_in_root"] = json.loads(req.POST.get("put_in_root"))
    if should_edit("display_separately"):
        module["display_separately"] = json.loads(req.POST.get("display_separately"))
    if should_edit("parent_module"):
        parent_module = req.POST.get("parent_module")
        module.parent_select.module_id = parent_module

    if should_edit('case_list_form_id'):
        module.case_list_form.form_id = req.POST.get('case_list_form_id')
    if should_edit('case_list_form_label'):
        module.case_list_form.label[lang] = req.POST.get('case_list_form_label')
    if should_edit('case_list_form_media_image'):
        val = _process_media_attribute(
            'case_list_form_media_image',
            resp,
            req.POST.get('case_list_form_media_image')
        )
        module.case_list_form.media_image = val
    if should_edit('case_list_form_media_audio'):
        val = _process_media_attribute(
            'case_list_form_media_audio',
            resp,
            req.POST.get('case_list_form_media_audio')
        )
        module.case_list_form.media_audio = val

    for attribute in ("name", "case_label", "referral_label"):
        if should_edit(attribute):
            name = req.POST.get(attribute, None)
            module[attribute][lang] = name
            if should_edit("name"):
                resp['update'].update({'.variable-module_name': module.name[lang]})
    for SLUG in ('case_list', 'task_list'):
        if should_edit(SLUG):
            module[SLUG].show = json.loads(req.POST['{SLUG}-show'.format(SLUG=SLUG)])
            module[SLUG].label[lang] = req.POST['{SLUG}-label'.format(SLUG=SLUG)]

    if isinstance(module, AdvancedModule):
        module.has_schedule = should_edit('has_schedule')
        if should_edit('has_schedule'):
            for form in module.get_forms():
                if not form.schedule:
                    form.schedule = FormSchedule()
        if should_edit("root_module_id"):
            if not req.POST.get("root_module_id"):
                module["root_module_id"] = None
            else:
                try:
                    app.get_module(module_id)
                    module["root_module_id"] = req.POST.get("root_module_id")
                except ModuleNotFoundException:
                    messages.error(_("Unknown Module"))

    _handle_media_edits(req, module, should_edit, resp)

    app.save(resp)
    resp['case_list-show'] = module.requires_case_details()
    return HttpResponse(json.dumps(resp))

@no_conflict_require_POST
@require_can_edit_apps
def edit_module_detail_screens(req, domain, app_id, module_id):
    """
    Overwrite module case details. Only overwrites components that have been
    provided in the request. Components are short, long, filter, parent_select,
    and sort_elements.
    """
    params = json_request(req.POST)
    detail_type = params.get('type')
    short = params.get('short', None)
    long = params.get('long', None)
    tabs = params.get('tabs', None)
    filter = params.get('filter', ())
    custom_xml = params.get('custom_xml', None)
    parent_select = params.get('parent_select', None)
    sort_elements = params.get('sort_elements', None)
    use_case_tiles = params.get('useCaseTiles', None)
    persist_tile_on_forms = params.get("persistTileOnForms", None)
    pull_down_tile = params.get("enableTilePullDown", None)

    app = get_app(domain, app_id)
    module = app.get_module(module_id)

    if detail_type == 'case':
        detail = module.case_details
    elif detail_type == CAREPLAN_GOAL:
        detail = module.goal_details
    elif detail_type == CAREPLAN_TASK:
        detail = module.task_details
    else:
        try:
            detail = getattr(module, '{0}_details'.format(detail_type))
        except AttributeError:
            return HttpResponseBadRequest("Unknown detail type '%s'" % detail_type)

    if short is not None:
        detail.short.columns = map(DetailColumn.wrap, short)
        if use_case_tiles is not None:
            detail.short.use_case_tiles = use_case_tiles
        if persist_tile_on_forms is not None:
            detail.short.persist_tile_on_forms = persist_tile_on_forms
        if pull_down_tile is not None:
            detail.short.pull_down_tile = pull_down_tile
    if long is not None:
        detail.long.columns = map(DetailColumn.wrap, long)
        if tabs is not None:
            detail.long.tabs = map(DetailTab.wrap, tabs)
    if filter != ():
        # Note that we use the empty tuple as the sentinel because a filter
        # value of None represents clearing the filter.
        detail.short.filter = filter
    if custom_xml is not None:
        detail.short.custom_xml = custom_xml
    if sort_elements is not None:
        detail.short.sort_elements = []
        for sort_element in sort_elements:
            item = SortElement()
            item.field = sort_element['field']
            item.type = sort_element['type']
            item.direction = sort_element['direction']
            detail.short.sort_elements.append(item)
    if parent_select is not None:
        module.parent_select = ParentSelect.wrap(parent_select)

    resp = {}
    app.save(resp)
    return json_response(resp)


def validate_module_for_build(request, domain, app_id, module_id, ajax=True):
    app = get_app(domain, app_id)
    try:
        module = app.get_module(module_id)
    except ModuleNotFoundException:
        raise Http404()
    errors = module.validate_for_build()
    lang, langs = get_langs(request, app)

    response_html = render_to_string('app_manager/partials/build_errors.html', {
        'app': app,
        'build_errors': errors,
        'not_actual_build': True,
        'domain': domain,
        'langs': langs,
        'lang': lang
    })
    if ajax:
        return json_response({'error_html': response_html})
    return HttpResponse(response_html)


def _process_media_attribute(attribute, resp, val):
    if val:
        if val.startswith('jr://'):
            pass
        elif val.startswith('/file/'):
            val = 'jr:/' + val
        elif val.startswith('file/'):
            val = 'jr://' + val
        elif val.startswith('/'):
            val = 'jr://file' + val
        else:
            val = 'jr://file/' + val
        resp['corrections'][attribute] = val
    else:
        val = None
    return val


def _handle_media_edits(request, item, should_edit, resp):
    if 'corrections' not in resp:
        resp['corrections'] = {}
    for attribute in ('media_image', 'media_audio'):
        if should_edit(attribute):
            val = _process_media_attribute(attribute, resp, request.POST.get(attribute))
            setattr(item, attribute, val)


@no_conflict_require_POST
@login_or_digest
@require_permission(Permissions.edit_apps, login_decorator=None)
def patch_xform(request, domain, app_id, unique_form_id):
    patch = request.POST['patch']
    sha1_checksum = request.POST['sha1']

    app = get_app(domain, app_id)
    form = app.get_form(unique_form_id)

    current_xml = form.source
    if hashlib.sha1(current_xml.encode('utf-8')).hexdigest() != sha1_checksum:
        return json_response({'status': 'conflict', 'xform': current_xml})

    dmp = diff_match_patch()
    xform, _ = dmp.patch_apply(dmp.patch_fromText(patch), current_xml)
    save_xform(app, form, xform)
    response_json = {
        'status': 'ok',
        'sha1': hashlib.sha1(form.source.encode('utf-8')).hexdigest()
    }
    app.save(response_json)
    return json_response(response_json)

@no_conflict_require_POST
@login_or_digest
@require_permission(Permissions.edit_apps, login_decorator=None)
def edit_form_attr(req, domain, app_id, unique_form_id, attr):
    """
    Called to edit any (supported) form attribute, given by attr

    """

    app = get_app(domain, app_id)
    form = app.get_form(unique_form_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    ajax = json.loads(req.POST.get('ajax', 'true'))

    resp = {}

    def should_edit(attribute):
        if req.POST.has_key(attribute):
            return True
        elif req.FILES.has_key(attribute):
            return True
        else:
            return False

    if should_edit("user_reg_data"):
        # should be user_registrations only
        data = json.loads(req.POST['user_reg_data'])
        data_paths = data['data_paths']
        data_paths_dict = {}
        for path in data_paths:
            data_paths_dict[path.split('/')[-1]] = path
        form.data_paths = data_paths_dict

    if should_edit("name"):
        name = req.POST['name']
        form.name[lang] = name
        xform = form.wrapped_xform()
        if xform.exists():
            xform.set_name(name)
            save_xform(app, form, xform.render())
        resp['update'] = {'.variable-form_name': form.name[lang]}
    if should_edit("xform"):
        try:
            # support FILES for upload and POST for ajax post from Vellum
            try:
                xform = req.FILES.get('xform').read()
            except Exception:
                xform = req.POST.get('xform')
            else:
                try:
                    xform = unicode(xform, encoding="utf-8")
                except Exception:
                    raise Exception("Error uploading form: Please make sure your form is encoded in UTF-8")
            if req.POST.get('cleanup', False):
                try:
                    # First, we strip all newlines and reformat the DOM.
                    px = parseString(xform.replace('\r\n', '')).toprettyxml()
                    # Then we remove excess newlines from the DOM output.
                    text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
                    prettyXml = text_re.sub('>\g<1></', px)
                    xform = prettyXml
                except Exception:
                    pass
            if xform:
                save_xform(app, form, xform)
            else:
                raise Exception("You didn't select a form to upload")
        except Exception, e:
            if ajax:
                return HttpResponseBadRequest(unicode(e))
            else:
                messages.error(req, unicode(e))
    if should_edit("show_count"):
        show_count = req.POST['show_count']
        form.show_count = True if show_count == "True" else False
    if should_edit("put_in_root"):
        put_in_root = req.POST['put_in_root']
        form.put_in_root = True if put_in_root == "True" else False
    if should_edit('form_filter'):
        form.form_filter = req.POST['form_filter']
    if should_edit('post_form_workflow'):
        form.post_form_workflow = req.POST['post_form_workflow']
    if should_edit('auto_gps_capture'):
        form.auto_gps_capture = req.POST['auto_gps_capture'] == 'true'
    if should_edit('no_vellum'):
        form.no_vellum = req.POST['no_vellum'] == 'true'
    if (should_edit("form_links_xpath_expressions") and
            should_edit("form_links_form_ids") and
            toggles.FORM_LINK_WORKFLOW.enabled(req.user.username)):
        form_links = zip(
            req.POST.getlist('form_links_xpath_expressions'),
            req.POST.getlist('form_links_form_ids')
        )
        form.form_links = [FormLink({'xpath': link[0], 'form_id': link[1]}) for link in form_links]

    _handle_media_edits(req, form, should_edit, resp)

    app.save(resp)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(req, domain, app_id=app_id, unique_form_id=unique_form_id)


@no_conflict_require_POST
@require_can_edit_apps
def edit_visit_schedule(request, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    json_loads = json.loads(request.POST.get('schedule'))
    form.schedule = FormSchedule.wrap(json_loads)
    response_json = {}
    app.save(response_json)
    return json_response(response_json)


@no_conflict_require_POST
@require_can_edit_apps
def rename_language(req, domain, form_unique_id):
    old_code = req.POST.get('oldCode')
    new_code = req.POST.get('newCode')
    try:
        form, app = Form.get_form(form_unique_id, and_app=True)
    except ResourceConflict:
        raise Http404()
    if app.domain != domain:
        raise Http404()
    try:
        form.rename_xform_language(old_code, new_code)
        app.save()
        return HttpResponse(json.dumps({"status": "ok"}))
    except XFormException as e:
        response = HttpResponse(json.dumps({'status': 'error', 'message': unicode(e)}))
        response.status_code = 409
        return response

@require_GET
@login_and_domain_required
def validate_language(request, domain, app_id):
    app = get_app(domain, app_id)
    term = request.GET.get('term', '').lower()
    if term in [lang.lower() for lang in app.langs]:
        return HttpResponse(json.dumps({'match': {"code": term, "name": term}, 'suggestions': []}))
    else:
        return HttpResponseRedirect("%s?%s" % (reverse('langcodes.views.validate', args=[]), django_urlencode({'term': term})))

@no_conflict_require_POST
@require_can_edit_apps
def edit_form_actions(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    form.actions = FormActions.wrap(json.loads(req.POST['actions']))
    form.requires = req.POST.get('requires', form.requires)
    response_json = {}
    app.save(response_json)
    response_json['propertiesMap'] = get_all_case_properties(app)
    return json_response(response_json)

@no_conflict_require_POST
@require_can_edit_apps
def edit_careplan_form_actions(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    transaction = json.loads(req.POST.get('transaction'))

    for question in transaction['fixedQuestions']:
        setattr(form, question['name'], question['path'])

    def to_dict(properties):
        return dict((p['key'], p['path']) for p in properties)

    form.custom_case_updates = to_dict(transaction['case_properties'])
    form.case_preload = to_dict(transaction['case_preload'])

    response_json = {}
    app.save(response_json)
    return json_response(response_json)


@no_conflict_require_POST
@require_can_edit_apps
def edit_advanced_form_actions(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    json_loads = json.loads(req.POST.get('actions'))
    actions = AdvancedFormActions.wrap(json_loads)
    form.actions = actions
    response_json = {}
    app.save(response_json)
    response_json['propertiesMap'] = get_all_case_properties(app)
    return json_response(response_json)


@require_can_edit_apps
def multimedia_list_download(req, domain, app_id):
    app = get_app(domain, app_id)
    include_audio = req.GET.get("audio", True)
    include_images = req.GET.get("images", True)
    strip_jr = req.GET.get("strip_jr", True)
    filelist = []
    for m in app.get_modules():
        for f in m.get_forms():
            parsed = XForm(f.source)
            parsed.validate(version=app.application_version)
            if include_images:
                filelist.extend(parsed.image_references)
            if include_audio:
                filelist.extend(parsed.audio_references)

    if strip_jr:
        filelist = [s.replace("jr://file/", "") for s in filelist if s]
    response = HttpResponse()
    set_file_download(response, 'list.txt')
    response.write("\n".join(sorted(set(filelist))))
    return response

@require_GET
@login_and_domain_required
def commcare_profile(req, domain, app_id):
    app = get_app(domain, app_id)
    return HttpResponse(json.dumps(app.profile))


@no_conflict_require_POST
@require_can_edit_apps
def edit_commcare_settings(request, domain, app_id):
    sub_responses = (
        edit_commcare_profile(request, domain, app_id),
        edit_app_attr(request, domain, app_id, 'all'),
    )
    response = {}
    for sub_response in sub_responses:
        response.update(
            json.loads(sub_response.content)
        )
    return json_response(response)

@no_conflict_require_POST
@require_can_edit_apps
def edit_commcare_profile(request, domain, app_id):
    try:
        settings = json.loads(request.body)
    except TypeError:
        return HttpResponseBadRequest(json.dumps({
            'reason': 'POST body must be of the form:'
                      '{"properties": {...}, "features": {...}}'
        }))
    app = get_app(domain, app_id)
    changed = defaultdict(dict)
    for type in ["features", "properties"]:
        for name, value in settings.get(type, {}).items():
            if type not in app.profile:
                app.profile[type] = {}
            app.profile[type][name] = value
            changed[type][name] = value
    response_json = {"status": "ok", "changed": changed}
    app.save(response_json)
    return json_response(response_json)


def validate_langs(request, existing_langs, validate_build=True):
    o = json.loads(request.body)
    langs = o['langs']
    rename = o['rename']
    build = o['build']

    assert set(rename.keys()).issubset(existing_langs)
    assert set(rename.values()).issubset(langs)
    # assert that there are no repeats in the values of rename
    assert len(set(rename.values())) == len(rename.values())
    # assert that no lang is renamed to an already existing lang
    for old, new in rename.items():
        if old != new:
            assert(new not in existing_langs)
    # assert that the build langs are in the correct order
    if validate_build:
        assert sorted(build, key=lambda lang: langs.index(lang)) == build

    return (langs, rename, build)


@no_conflict_require_POST
@require_can_edit_apps
def edit_app_langs(request, domain, app_id):
    """
    Called with post body:
    {
        langs: ["en", "es", "hin"],
        rename: {
            "hi": "hin",
            "en": "en",
            "es": "es"
        },
        build: ["es", "hin"]
    }
    """
    app = get_app(domain, app_id)
    try:
        langs, rename, build = validate_langs(request, app.langs)
    except AssertionError:
        return HttpResponse(status=400)

    # now do it
    for old, new in rename.items():
        if old != new:
            app.rename_lang(old, new)

    def replace_all(list1, list2):
        if list1 != list2:
            while list1:
                list1.pop()
            list1.extend(list2)
    replace_all(app.langs, langs)
    replace_all(app.build_langs, build)

    app.save()
    return json_response(langs)


@require_can_edit_apps
@no_conflict_require_POST
def edit_app_translations(request, domain, app_id):
    params = json_request(request.POST)
    lang = params.get('lang')
    translations = params.get('translations')
    app = get_app(domain, app_id)
    app.set_translations(lang, translations)
    response = {}
    app.save(response)
    return json_response(response)


@require_GET
def get_app_translations(request, domain):
    params = json_request(request.GET)
    lang = params.get('lang', 'en')
    key = params.get('key', None)
    one = params.get('one', False)
    translations = Translation.get_translations(lang, key, one)
    if isinstance(translations, dict):
        translations = {k: v for k, v in translations.items()
                        if not id_strings.is_custom_app_string(k)
                        and '=' not in k}
    return json_response(translations)


@no_conflict_require_POST
@require_can_edit_apps
def delete_app_lang(req, domain, app_id):
    """
    DEPRECATED
    Called when a language (such as 'zh') is to be deleted from app.langs

    """
    lang_id = int(req.POST['index'])
    app = get_app(domain, app_id)
    del app.langs[lang_id]
    app.save()
    return back_to_main(req, domain, app_id=app_id)


@no_conflict_require_POST
@require_can_edit_apps
def edit_app_attr(request, domain, app_id, attr):
    """
    Called to edit any (supported) app attribute, given by attr

    """
    app = get_app(domain, app_id)
    lang = request.COOKIES.get('lang', (app.langs or ['en'])[0])

    try:
        hq_settings = json.loads(request.body)['hq']
    except ValueError:
        hq_settings = request.POST

    attributes = [
        'all',
        'recipients', 'name', 'success_message', 'use_commcare_sense',
        'text_input', 'platform', 'build_spec', 'show_user_registration',
        'use_custom_suite', 'custom_suite',
        'admin_password',
        # Application only
        'cloudcare_enabled',
        'application_version',
        'case_sharing',
        'translation_strategy',
        'auto_gps_capture',
        # RemoteApp only
        'profile_url',
        'manage_urls'
        ]
    if attr not in attributes:
        return HttpResponseBadRequest()

    def should_edit(attribute):
        return attribute == attr or ('all' == attr and attribute in hq_settings)
    resp = {"update": {}}
    # For either type of app
    easy_attrs = (
        ('application_version', None),
        ('build_spec', BuildSpec.from_string),
        ('case_sharing', None),
        ('cloudcare_enabled', None),
        ('commtrack_enabled', None),
        ('commtrack_requisition_mode', lambda m: None if m == 'disabled' else m),
        ('manage_urls', None),
        ('name', None),
        ('platform', None),
        ('recipients', None),
        ('text_input', None),
        ('use_custom_suite', None),
        ('secure_submissions', None),
        ('translation_strategy', None),
        ('auto_gps_capture', None),
        ('amplifies_workers', None),
        ('amplifies_project', None),
    )
    for attribute, transformation in easy_attrs:
        if should_edit(attribute):
            value = hq_settings[attribute]
            if transformation:
                value = transformation(value)
            setattr(app, attribute, value)

    if should_edit("name"):
        _clear_app_cache(request, domain)
        name = hq_settings['name']
        resp['update'].update({
            '.variable-app_name': name,
            '[data-id="{id}"]'.format(id=app_id): ApplicationsTab.make_app_title(name, app.doc_type),
        })

    if should_edit("success_message"):
        success_message = hq_settings['success_message']
        app.success_message[lang] = success_message

    if should_edit("build_spec"):
        resp['update']['commcare-version'] = app.commcare_minor_release

    if should_edit("admin_password"):
        admin_password = hq_settings.get('admin_password')
        if admin_password:
            app.set_admin_password(admin_password)

    # For Normal Apps
    if should_edit("cloudcare_enabled"):
        if app.get_doc_type() not in ("Application",):
            raise Exception("App type %s does not support cloudcare" % app.get_doc_type())
        try:
            ensure_request_has_privilege(request, privileges.CLOUDCARE)
        except PermissionDenied:
            app.cloudcare_enabled = False

    if should_edit('show_user_registration'):
        show_user_registration = hq_settings['show_user_registration']
        app.show_user_registration = show_user_registration
        if show_user_registration:
            #  load the form source and also set its unique_id
            app.get_user_registration()

    def require_remote_app():
        if app.get_doc_type() not in ("RemoteApp",):
            raise Exception("App type %s does not support profile url" % app.get_doc_type())

    # For RemoteApps
    if should_edit("profile_url"):
        require_remote_app()
        app['profile_url'] = hq_settings['profile_url']
    if should_edit("manage_urls"):
        require_remote_app()

    app.save(resp)
    # this is a put_attachment, so it has to go after everything is saved
    if should_edit("custom_suite"):
        app.set_custom_suite(hq_settings['custom_suite'])

    return HttpResponse(json.dumps(resp))


@no_conflict_require_POST
@require_can_edit_apps
def rearrange(req, domain, app_id, key):
    """
    This function handles any request to switch two items in a list.
    Key tells us the list in question and must be one of
    'forms', 'modules', 'detail', or 'langs'. The two POST params
    'to' and 'from' give us the indicies of the items to be rearranged.

    """
    app = get_app(domain, app_id)
    ajax = json.loads(req.POST.get('ajax', 'false'))
    i, j = (int(x) for x in (req.POST['to'], req.POST['from']))
    resp = {}
    module_id = None

    try:
        if "forms" == key:
            to_module_id = int(req.POST['to_module_id'])
            from_module_id = int(req.POST['from_module_id'])
            try:
                app.rearrange_forms(to_module_id, from_module_id, i, j)
            except ConflictingCaseTypeError:
                messages.warning(req, CASE_TYPE_CONFLICT_MSG,  extra_tags="html")
        elif "modules" == key:
            app.rearrange_modules(i, j)
    except IncompatibleFormTypeException:
        messages.error(req, _(
            'The form can not be moved into the desired module.'
        ))
        return back_to_main(req, domain, app_id=app_id, module_id=module_id)
    except (RearrangeError, ModuleNotFoundException):
        messages.error(req, _(
            'Oops. '
            'Looks like you got out of sync with us. '
            'The sidebar has been updated, so please try again.'
        ))
        return back_to_main(req, domain, app_id=app_id, module_id=module_id)
    app.save(resp)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(req, domain, app_id=app_id, module_id=module_id)


# The following three functions deal with
# Saving multiple versions of the same app
# i.e. "making builds"


@no_conflict_require_POST
@require_can_edit_apps
def save_copy(req, domain, app_id):
    """
    Saves a copy of the app to a new doc.
    See VersionedDoc.save_copy

    """
    comment = req.POST.get('comment')
    app = get_app(domain, app_id)
    errors = app.validate_app()

    if not errors:
        try:
            copy = app.make_build(
                comment=comment,
                user_id=req.couch_user.get_id,
                previous_version=app.get_latest_app(released_only=False)
            )
            copy.save(increment_version=False)
        finally:
            # To make a RemoteApp always available for building
            if app.is_remote_app():
                app.save(increment_version=True)
    else:
        copy = None
    copy = copy and SavedAppBuild.wrap(copy.to_json()).to_saved_build_json(
        report_utils.get_timezone(req.couch_user, domain)
    )
    lang, langs = get_langs(req, app)
    return json_response({
        "saved_app": copy,
        "error_html": render_to_string('app_manager/partials/build_errors.html', {
            'app': get_app(domain, app_id),
            'build_errors': errors,
            'domain': domain,
            'langs': langs,
            'lang': lang
        }),
    })


def validate_form_for_build(request, domain, app_id, unique_form_id, ajax=True):
    app = get_app(domain, app_id)
    try:
        form = app.get_form(unique_form_id)
    except FormNotFoundException:
        # this can happen if you delete the form from another page
        raise Http404()
    errors = form.validate_for_build()
    lang, langs = get_langs(request, app)

    if ajax and "blank form" in [error.get('type') for error in errors]:
        response_html = render_to_string('app_manager/partials/create_form_prompt.html')
    else:
        response_html = render_to_string('app_manager/partials/build_errors.html', {
            'app': app,
            'form': form,
            'build_errors': errors,
            'not_actual_build': True,
            'domain': domain,
            'langs': langs,
            'lang': lang
        })

    if ajax:
        return json_response({
            'error_html': response_html,
        })
    else:
        return HttpResponse(response_html)


@no_conflict_require_POST
@require_can_edit_apps
def revert_to_copy(req, domain, app_id):
    """
    Copies a saved doc back to the original.
    See VersionedDoc.revert_to_copy

    """
    app = get_app(domain, app_id)
    copy = get_app(domain, req.POST['saved_app'])
    app = app.make_reversion_to_copy(copy)
    app.save()
    messages.success(req, "Successfully reverted to version %s, now at version %s" % (copy.version, app.version))
    return back_to_main(req, domain, app_id=app_id)

@no_conflict_require_POST
@require_can_edit_apps
def delete_copy(req, domain, app_id):
    """
    Deletes a saved copy permanently from the database.
    See VersionedDoc.delete_copy

    """
    app = get_app(domain, app_id)
    copy = get_app(domain, req.POST['saved_app'])
    app.delete_copy(copy)
    return json_response({})


# download_* views are for downloading the files that the application generates
# (such as CommCare.jad, suite.xml, profile.xml, etc.

BAD_BUILD_MESSAGE = "Sorry: this build is invalid. Try deleting it and rebuilding. If error persists, please contact us at commcarehq-support@dimagi.com"


def _download_index_files(request):
    files = []
    if request.app.copy_of:
        files = [(path[len('files/'):], request.app.fetch_attachment(path))
                 for path in request.app._attachments
                 if path.startswith('files/')]
    else:
        try:
            files = request.app.create_all_files().items()
        except Exception:
            messages.error(request, _(
                "We were unable to get your files "
                "because your Application has errors. "
                "Please click <strong>Make New Version</strong> "
                "under <strong>Deploy</strong> "
                "for feedback on how to fix these errors."
            ), extra_tags='html')
    return sorted(files)


@safe_download
def download_index(req, domain, app_id, template="app_manager/download_index.html"):
    """
    A landing page, mostly for debugging, that has links the jad and jar as well as
    all the resource files that will end up zipped into the jar.

    """
    return render(req, template, {
        'app': req.app,
        'files': _download_index_files(req),
    })


class DownloadCCZ(DownloadMultimediaZip):
    name = 'download_ccz'
    compress_zip = True
    zip_name = 'commcare.ccz'

    def check_before_zipping(self):
        pass

    def iter_files(self):
        skip_files = ('profile.xml', 'profile.ccpr', 'media_profile.xml')
        text_extensions = ('.xml', '.ccpr', '.txt')
        get_name = lambda f: {'media_profile.ccpr': 'profile.ccpr'}.get(f, f)

        def _files():
            for name, f in _download_index_files(self.request):
                if name not in skip_files:
                    # TODO: make RemoteApp.create_all_files not return media files
                    extension = os.path.splitext(name)[1]
                    data = _encode_if_unicode(f) if extension in text_extensions else f
                    yield (get_name(name), data)

        if self.app.is_remote_app():
            return _files(), []
        else:
            media_files, errors = super(DownloadCCZ, self).iter_files()
            return itertools.chain(_files(), media_files), errors



@safe_download
def download_file(req, domain, app_id, path):
    mimetype_map = {
        'ccpr': 'commcare/profile',
        'jad': 'text/vnd.sun.j2me.app-descriptor',
        'jar': 'application/java-archive',
        'xml': 'application/xml',
        'txt': 'text/plain',
    }
    try:
        mimetype = mimetype_map[path.split('.')[-1]]
    except KeyError:
        mimetype = None
    response = HttpResponse(mimetype=mimetype)

    if path in ('CommCare.jad', 'CommCare.jar'):
        set_file_download(response, path)
        full_path = path
    else:
        full_path = 'files/%s' % path

    def resolve_path(path):
        return RegexURLResolver(
            r'^', 'corehq.apps.app_manager.download_urls').resolve(path)

    try:
        assert req.app.copy_of
        obj = CachedObject('{id}::{path}'.format(
            id=req.app._id,
            path=full_path,
        ))
        if not obj.is_cached():
            payload = req.app.fetch_attachment(full_path)
            if type(payload) is unicode:
                payload = payload.encode('utf-8')
            buffer = StringIO(payload)
            metadata = {'content_type': mimetype}
            obj.cache_put(buffer, metadata, timeout=0)
        else:
            _, buffer = obj.get()
            payload = buffer.getvalue()
        response.write(payload)
        response['Content-Length'] = len(response.content)
        return response
    except (ResourceNotFound, AssertionError):
        if req.app.copy_of:
            if req.META.get('HTTP_USER_AGENT') == 'bitlybot':
                raise Http404()
            elif path == 'profile.ccpr':
                # legacy: should patch build to add odk profile
                # which wasn't made on build for a long time
                add_odk_profile_after_build(req.app)
                req.app.save()
                return download_file(req, domain, app_id, path)
            else:
                try:
                    resolve_path(path)
                except Resolver404:
                    # ok this was just a url that doesn't exist
                    # todo: log since it likely exposes a mobile bug
                    # logging was removed because such a mobile bug existed
                    # and was spamming our emails
                    pass
                else:
                    # this resource should exist but doesn't
                    logging.error(
                        'Expected build resource %s not found' % path,
                        extra={'request': req}
                    )
                    if not req.app.build_broken:
                        req.app.build_broken = True
                        req.app.build_broken_reason = 'incomplete-build'
                        try:
                            req.app.save()
                        except ResourceConflict:
                            # this really isn't a big deal:
                            # It'll get updated next time a resource is req'd;
                            # in fact the conflict is almost certainly from
                            # another thread doing this exact update
                            pass
                raise Http404()
        try:
            callback, callback_args, callback_kwargs = resolve_path(path)
        except Resolver404:
            raise Http404()

        return callback(req, domain, app_id, *callback_args, **callback_kwargs)


@safe_download
def download_profile(req, domain, app_id):
    """
    See ApplicationBase.create_profile

    """
    return HttpResponse(
        req.app.create_profile()
    )

@safe_download
def download_media_profile(req, domain, app_id):
    return HttpResponse(
        req.app.create_profile(with_media=True)
    )

def odk_install(req, domain, app_id, with_media=False):
    app = get_app(domain, app_id)
    qr_code_view = "odk_qr_code" if not with_media else "odk_media_qr_code"
    context = {
        "domain": domain,
        "app": app,
        "qr_code": reverse("corehq.apps.app_manager.views.%s" % qr_code_view, args=[domain, app_id]),
        "profile_url": app.odk_profile_display_url if not with_media else app.odk_media_profile_display_url,
    }
    return render(req, "app_manager/odk_install.html", context)

def odk_qr_code(req, domain, app_id):
    qr_code = get_app(domain, app_id).get_odk_qr_code()
    return HttpResponse(qr_code, mimetype="image/png")

def odk_media_qr_code(req, domain, app_id):
    qr_code = get_app(domain, app_id).get_odk_qr_code(with_media=True)
    return HttpResponse(qr_code, mimetype="image/png")

@safe_download
def download_odk_profile(req, domain, app_id):
    """
    See ApplicationBase.create_profile

    """
    return HttpResponse(
        req.app.create_profile(is_odk=True),
        mimetype="commcare/profile"
    )

@safe_download
def download_odk_media_profile(req, domain, app_id):
    return HttpResponse(
        req.app.create_profile(is_odk=True, with_media=True),
        mimetype="commcare/profile"
    )

@safe_download
def download_suite(req, domain, app_id):
    """
    See Application.create_suite

    """
    return HttpResponse(
        req.app.create_suite()
    )

@safe_download
def download_media_suite(req, domain, app_id):
    """
    See Application.create_media_suite

    """
    return HttpResponse(
        req.app.create_media_suite()
    )


@safe_download
def download_app_strings(req, domain, app_id, lang):
    """
    See Application.create_app_strings

    """
    return HttpResponse(
        req.app.create_app_strings(lang)
    )


@safe_download
def download_xform(req, domain, app_id, module_id, form_id):
    """
    See Application.fetch_xform

    """
    try:
        return HttpResponse(
            req.app.fetch_xform(module_id, form_id)
        )
    except (IndexError, ModuleNotFoundException):
        raise Http404()
    except AppManagerException:
        unique_form_id = req.app.get_module(module_id).get_form(form_id).unique_id
        response = validate_form_for_build(req, domain, app_id, unique_form_id, ajax=False)
        response.status_code = 404
        return response


@safe_download
def download_user_registration(req, domain, app_id):
    """See Application.fetch_xform"""
    return HttpResponse(
        req.app.get_user_registration().render_xform()
    )


@safe_download
def download_jad(req, domain, app_id):
    """
    See ApplicationBase.create_jadjar

    """
    app = req.app
    try:
        jad, _ = app.create_jadjar()
    except ResourceConflict:
        return download_jad(req, domain, app_id)
    try:
        response = HttpResponse(jad)
    except Exception:
        messages.error(req, BAD_BUILD_MESSAGE)
        return back_to_main(req, domain, app_id=app_id)
    set_file_download(response, "CommCare.jad")
    response["Content-Type"] = "text/vnd.sun.j2me.app-descriptor"
    response["Content-Length"] = len(jad)
    return response

@safe_download
def download_jar(req, domain, app_id):
    """
    See ApplicationBase.create_jadjar

    This is the only view that will actually be called
    in the process of downloading a complete CommCare.jar
    build (i.e. over the air to a phone).

    """
    response = HttpResponse(mimetype="application/java-archive")
    app = req.app
    _, jar = app.create_jadjar()
    set_file_download(response, 'CommCare.jar')
    response['Content-Length'] = len(jar)
    try:
        response.write(jar)
    except Exception:
        messages.error(req, BAD_BUILD_MESSAGE)
        return back_to_main(req, domain, app_id=app_id)
    return response

def download_test_jar(request):
    with open(os.path.join(os.path.dirname(__file__), 'static', 'app_manager', 'CommCare.jar')) as f:
        jar = f.read()

    response = HttpResponse(mimetype="application/java-archive")
    set_file_download(response, "CommCare.jar")
    response['Content-Length'] = len(jar)
    response.write(jar)
    return response

@safe_download
def download_raw_jar(req, domain, app_id):
    """
    See ApplicationBase.fetch_jar

    """
    response = HttpResponse(
        req.app.fetch_jar()
    )
    response['Content-Type'] = "application/java-archive"
    return response


@require_can_edit_apps
def formdefs(request, domain, app_id):
    langs = [json.loads(request.GET.get('lang', '"en"'))]
    format = request.GET.get('format', 'json')
    app = get_app(domain, app_id)

    def get_questions(form):
        xform = XForm(form.source)
        prefix = '/%s/' % xform.data_node.tag_name
        def remove_prefix(string):
            if string.startswith(prefix):
                return string[len(prefix):]
            else:
                raise Exception()
        def transform_question(q):
            return {
                'id': remove_prefix(q['value']),
                'type': q['tag'],
                'text': q['label'] if q['tag'] != 'hidden' else ''
            }
        return [transform_question(q) for q in xform.get_questions(langs)]
    formdefs = [{
        'name': "%s, %s" % (f['form'].get_module().name['en'], f['form'].name['en']) if f['type'] == 'module_form' else 'User Registration',
        'columns': ['id', 'type', 'text'],
        'rows': get_questions(f['form'])
    } for f in app.get_forms(bare=False)]

    if format == 'xlsx':
        f = StringIO()
        writer = Excel2007ExportWriter()
        writer.open([(sheet['name'], [FormattedRow(sheet['columns'])]) for sheet in formdefs], f)
        writer.write([(
            sheet['name'],
            [FormattedRow([cell for (_, cell) in sorted(row.items(), key=lambda item: sheet['columns'].index(item[0]))]) for row in sheet['rows']]
        ) for sheet in formdefs])
        writer.close()
        response = HttpResponse(f.getvalue(), mimetype=Format.from_format('xlsx').mimetype)
        set_file_download(response, 'formdefs.xlsx')
        return response
    else:
        return json_response(formdefs)

def _questions_for_form(request, form, langs):
    class FakeMessages(object):
        def __init__(self):
            self.messages = defaultdict(list)

        def add_message(self, type, message):
            self.messages[type].append(message)

        def error(self, request, message, *args, **kwargs):
            self.add_message('error', message)

        def warning(self, request, message, *args, **kwargs):
            self.add_message('warning', message)

    m = FakeMessages()

    _, context = get_form_view_context_and_template(request, form, langs, None, messages=m)
    xform_questions = context['xform_questions']
    return xform_questions, m.messages

def _find_name(names, langs):
    name = None
    for lang in langs:
        if lang in names:
            name = names[lang]
            break
    if name is None:
        lang = names.keys()[0]
        name = names[lang]
    return name


class AppSummaryView(JSONResponseMixin, LoginAndDomainMixin, BasePageView, ApplicationViewMixin):
    urlname = 'app_summary'
    page_title = ugettext_noop("Summary")
    template_name = 'app_manager/summary_new.html'

    def dispatch(self, request, *args, **kwargs):
        request.preview_bootstrap3 = True
        return super(AppSummaryView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(AppSummaryView, self).main_context
        context.update({
            'domain': self.domain,
        })
        return context

    @property
    def page_context(self):
        if not self.app or self.app.doc_type == 'RemoteApp':
            raise Http404()

        form_name_map = {}
        for module in self.app.get_modules():
            for form in module.get_forms():
                form_name_map[form.unique_id] = {
                    'module_name': module.name,
                    'form_name': form.name
                }

        return {
            'VELLUM_TYPES': VELLUM_TYPES,
            'form_name_map': form_name_map,
            'langs': self.app.langs,
        }

    @property
    def parent_pages(self):
        return [
            {
                'title': _("Applications"),
                'url': reverse('view_app', args=[self.domain, self.app_id]),
            },
            {
                'title': self.app.name,
                'url': reverse('view_app', args=[self.domain, self.app_id]),
            }
        ]

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.app_id])

    @allow_remote_invocation
    def get_case_data(self, in_data):
        return {
            'response': self.app.get_case_metadata().to_json(),
            'success': True,
        }

    @allow_remote_invocation
    def get_form_data(self, in_data):
        modules = []
        for module in self.app.get_modules():
            forms = []
            for form in module.get_forms():
                questions = form.get_questions(self.app.langs, include_triggers=True, include_groups=True)
                forms.append({
                    'id': form.unique_id,
                    'name': _find_name(form.name, self.app.langs),
                    'questions': [FormQuestionResponse(q).to_json() for q in questions],
                })

            modules.append({
                'id': module.unique_id,
                'name': _find_name(module.name, self.app.langs),
                'forms': forms
            })
        return {
            'response': modules,
            'success': True,
        }


def get_default_translations_for_download(app):
    return app_strings.CHOICES[app.translation_strategy].get_default_translations('en')


def get_index_for_defaults(langs):
    try:
        return langs.index("en")
    except ValueError:
        return 0


def build_ui_translation_download_file(app):

    properties = tuple(["property"] + app.langs + ["platform"])
    temp = StringIO()
    headers = (("translations", properties),)

    row_dict = {}
    for i, lang in enumerate(app.langs):
        index = i + 1
        trans_dict = app.translations.get(lang, {})
        for prop, trans in trans_dict.iteritems():
            if prop not in row_dict:
                row_dict[prop] = [prop]
            num_to_fill = index - len(row_dict[prop])
            row_dict[prop].extend(["" for i in range(num_to_fill)] if num_to_fill > 0 else [])
            row_dict[prop].append(trans)

    rows = row_dict.values()
    all_prop_trans = get_default_translations_for_download(app)
    rows.extend([[t] for t in sorted(all_prop_trans.keys()) if t not in row_dict])

    def fillrow(row):
        num_to_fill = len(properties) - len(row)
        row.extend(["" for i in range(num_to_fill)] if num_to_fill > 0 else [])
        return row

    def add_default(row):
        row_index = get_index_for_defaults(app.langs) + 1
        if not row[row_index]:
            # If no custom translation exists, replace it.
            row[row_index] = all_prop_trans.get(row[0], "")
        return row

    def add_sources(row):
        platform_map = {
            "CommCareAndroid": "Android",
            "CommCareJava": "Java",
            "ODK": "Android",
            "JavaRosa": "Java",
        }
        source = system_text_sources.SOURCES.get(row[0], "")
        row[-1] = platform_map.get(source, "")
        return row

    rows = [add_sources(add_default(fillrow(row))) for row in rows]

    data = (("translations", tuple(rows)),)
    export_raw(headers, data, temp)
    return temp


@require_can_edit_apps
def download_bulk_ui_translations(request, domain, app_id):
    app = get_app(domain, app_id)
    temp = build_ui_translation_download_file(app)
    return export_response(temp, Format.XLS_2007, "translations")


def process_ui_translation_upload(app, trans_file):

    workbook = WorkbookJSONReader(trans_file)
    translations = workbook.get_worksheet(title='translations')

    default_trans = get_default_translations_for_download(app)
    lang_with_defaults = app.langs[get_index_for_defaults(app.langs)]
    trans_dict = defaultdict(dict)
    error_properties = []
    for row in translations:
        for lang in app.langs:
            if row.get(lang):
                all_parameters = re.findall("\$.*?}", row[lang])
                for param in all_parameters:
                    if not re.match("\$\{[0-9]+}", param):
                        error_properties.append(row["property"] + ' - ' + row[lang])
                if not (lang_with_defaults == lang
                        and row[lang] == default_trans.get(row["property"], "")):
                    trans_dict[lang].update({row["property"]: row[lang]})
    return trans_dict, error_properties


@no_conflict_require_POST
@require_can_edit_apps
@get_file("bulk_upload_file")
def upload_bulk_ui_translations(request, domain, app_id):
    success = False
    try:
        app = get_app(domain, app_id)
        trans_dict, error_properties = process_ui_translation_upload(
            app, request.file
        )
        if error_properties:
            message = _("We found problem with following translations:")
            message += "<br>"
            for prop in error_properties:
                message += "<li>%s</li>" % prop
            messages.error(request, message, extra_tags='html')
        else:
            app.translations = dict(trans_dict)
            app.save()
            success = True
    except Exception:
        notify_exception(request, 'Bulk Upload Translations Error')
        messages.error(request, _("Something went wrong! Update failed. We're looking into it"))

    if success:
        messages.success(request, _("UI Translations Updated!"))

    return HttpResponseRedirect(reverse('app_languages', args=[domain, app_id]))


@require_can_edit_apps
def download_bulk_app_translations(request, domain, app_id):
    app = get_app(domain, app_id)
    headers = expected_bulk_app_sheet_headers(app)
    rows = expected_bulk_app_sheet_rows(app)
    temp = StringIO()
    data = [(k, v) for k, v in rows.iteritems()]
    export_raw(headers, data, temp)
    return export_response(temp, Format.XLS_2007, "bulk_app_translations")


@no_conflict_require_POST
@require_can_edit_apps
@get_file("bulk_upload_file")
def upload_bulk_app_translations(request, domain, app_id):
    app = get_app(domain, app_id)
    msgs = process_bulk_app_translation_upload(app, request.file)
    app.save()
    for msg in msgs:
        # Add the messages to the request object.
        # msg[0] should be a function like django.contrib.messages.error .
        # mes[1] should be a string.
        msg[0](request, msg[1])
    return HttpResponseRedirect(
        reverse('app_languages', args=[domain, app_id])
    )

@require_deploy_apps
def update_build_comment(request, domain, app_id):
    build_id = request.POST.get('build_id')
    try:
        build = SavedAppBuild.get(build_id)
    except ResourceNotFound:
        raise Http404()
    build.build_comment = request.POST.get('comment')
    build.save()
    return json_response({'status': 'success'})


common_module_validations = [
    (lambda app: app.application_version == APP_V1,
     _('Please upgrade you app to > 2.0 in order to add a Careplan module'))
]


FN = 'fn'
VALIDATIONS = 'validations'
MODULE_TYPE_MAP = {
    'careplan': {
        FN: _new_careplan_module,
        VALIDATIONS: common_module_validations + [
            (lambda app: app.has_careplan_module,
             _('This application already has a Careplan module'))
        ]
    },
    'advanced': {
        FN: _new_advanced_module,
        VALIDATIONS: common_module_validations
    }
}
