from StringIO import StringIO
import logging
import hashlib
from lxml import etree
import os
import re
import json
from collections import defaultdict
from xml.dom.minidom import parseString

from diff_match_patch import diff_match_patch
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _, get_language
from django.views.decorators.cache import cache_control
from corehq import ApplicationsTab, toggles
from corehq.apps.app_manager import commcare_settings
from corehq.apps.app_manager.exceptions import (
    AppManagerException,
    BlankXFormError,
    ConflictingCaseTypeError,
    RearrangeError,
)
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.sms.views import get_sms_autocomplete_context
from django.utils.http import urlencode as django_urlencode
from couchdbkit.exceptions import ResourceConflict
from django.http import HttpResponse, Http404, HttpResponseBadRequest, HttpResponseForbidden
from unidecode import unidecode
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse, RegexURLResolver
from django.shortcuts import render
from dimagi.utils.django.cached_object import CachedObject
from django.utils.http import urlencode
from django.views.decorators.http import require_GET
from django.conf import settings
from couchdbkit.resource import ResourceNotFound
from corehq.apps.app_manager.const import APP_V1, CAREPLAN_GOAL, CAREPLAN_TASK, APP_V2
from corehq.apps.app_manager.success_message import SuccessMessage
from corehq.apps.app_manager.util import is_valid_case_type, get_all_case_properties, add_odk_profile_after_build, ParentCasePropertyBuilder
from corehq.apps.app_manager.util import save_xform, get_settings_values
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.translations import system_text as st_trans
from corehq.util.compression import decompress
from couchexport.export import FormattedRow, export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from couchexport.writers import Excel2007ExportWriter
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.resource_conflict import retry_resource
from corehq.apps.app_manager.xform import XFormError, XFormValidationError, CaseError,\
    XForm
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions, CommCareUser
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.decorators.view import get_file
from dimagi.utils.django.cache import make_template_fragment_key
from dimagi.utils.excel import WorkbookJSONReader
from dimagi.utils.logging import notify_exception
from dimagi.utils.subprocess_timeout import ProcessTimedOut
from dimagi.utils.web import json_response, json_request
from corehq.apps.reports import util as report_utils
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest
from corehq.apps.app_manager.models import Application, get_app, DetailColumn, Form, FormActions,\
    AppEditingError, load_case_reserved_words, ApplicationBase, DeleteFormRecord, DeleteModuleRecord, \
    DeleteApplicationRecord, str_to_cls, validate_lang, SavedAppBuild, ParentSelect, Module, CareplanModule, CareplanForm, CareplanGoalForm, CareplanTaskForm
from corehq.apps.app_manager.models import DETAIL_TYPES, import_app as import_app_util, SortElement
from dimagi.utils.web import get_url_base
from corehq.apps.app_manager.decorators import safe_download, no_conflict_require_POST
from django.contrib import messages
from toggle import toggle_enabled

logger = logging.getLogger(__name__)

require_can_edit_apps = require_permission(Permissions.edit_apps)


def set_file_download(response, filename):
    response["Content-Disposition"] = "attachment; filename=%s" % filename


def _encode_if_unicode(s):
    return s.encode('utf-8') if isinstance(s, unicode) else s

CASE_TYPE_CONFLICT_MSG = (
    "Warning: The form's new module "
    "has a different case type from the old module.<br />"
    "Make sure all case properties you are loading "
    "are available in the new case type"
)


class ApplicationViewMixin(DomainViewMixin):
    """
    Helper for class-based views in app manager

    Currently only used in hqmedia

    """

    @property
    @memoized
    def app_id(self):
        return self.args[1] if len(self.args) > 1 else self.kwargs.get('app_id')

    @property
    @memoized
    def app(self):
        try:
            # if get_app is mainly used for views,
            # maybe it should be a classmethod of this mixin? todo
            return get_app(self.domain, self.app_id)
        except Exception:
            pass
        return None


@login_and_domain_required
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

@login_and_domain_required
def get_xform_source(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    try:
        form = app.get_module(module_id).get_form(form_id)
    except IndexError:
        raise Http404()
    return _get_xform_source(req, app, form)

@login_and_domain_required
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

    questions = form.get_questions(langs)

    return HttpResponse(json.dumps(questions))

@login_and_domain_required
def form_casexml(req, domain, form_unique_id):
    try:
        form, app = Form.get_form(form_unique_id, and_app=True)
    except ResourceNotFound:
        raise Http404()
    if domain != app.domain:
        raise Http404()
    return HttpResponse(form.create_casexml())

@login_or_digest
def app_source(req, domain, app_id):
    app = get_app(domain, app_id)
    return HttpResponse(app.export_json())

@login_and_domain_required
def copy_app_check_domain(req, domain):
    app_id = req.GET.get('app')
    name = req.GET.get('name')

    app_copy = import_app_util(app_id, domain, name=name)
    return back_to_main(req, app_copy.domain, app_id=app_copy._id)

@login_and_domain_required
def copy_app(req, domain):
    return copy_app_check_domain(req, req.GET.get('domain'))

@login_and_domain_required
def import_app(req, domain, template="app_manager/import_app.html"):
    if req.method == "POST":
        _clear_app_cache(req, domain)
        name = req.POST.get('name')
        compressed = req.POST.get('compressed')
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
    except XFormError as e:
        form_errors.append("Error in form: %s" % e)
    except Exception as e:
        logging.exception(e)
        form_errors.append("Unexpected error in form: %s" % e)

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
            form_errors.append("Syntax Error: %s" % e)
        except AppEditingError as e:
            form_errors.append("Error in application: %s" % e)
        except XFormValidationError:
            xform_validation_errored = True
            # showing these messages is handled by validate_form_for_build ajax
            pass
        except XFormError as e:
            form_errors.append("Error in form: %s" % e)
        # any other kind of error should fail hard,
        # but for now there are too many for that to be practical
        except Exception as e:
            if settings.DEBUG:
                raise
            notify_exception(request, 'Unexpected Build Error')
            form_errors.append("Unexpected System Error: %s" % e)

        try:
            form_action_errors = form.validate_for_build()
            if not form_action_errors:
                form.add_stuff_to_xform(xform)
                if settings.DEBUG and False:
                    xform.validate()
        except CaseError as e:
            messages.error(request, "Error in Case Management: %s" % e)
        except XFormValidationError as e:
            messages.error(request, "%s" % e)
        except Exception as e:
            if settings.DEBUG:
                raise
            logging.exception(e)
            messages.error(request, "Unexpected Error: %s" % e)

    try:
        languages = xform.get_languages()
    except Exception:
        languages = []

    for i, err in enumerate(form_errors):
        if not isinstance(err, basestring):
            messages.error(request, err[0], **err[1])
            form_errors[i] = err[0]
        else:
            messages.error(request, err)

    module_case_types = [
        {'module_name': trans(module.name, langs),
         'case_type': module.case_type}
        for module in form.get_app().modules if module.case_type
    ] if not is_user_registration else None

    context = {
        'nav_form': form if not is_user_registration else '',
        'xform_languages': languages,
        "xform_questions": xform_questions,
        'case_reserved_words_json': load_case_reserved_words(),
        'module_case_types': module_case_types,
        'form_errors': form_errors,
        'xform_validation_errored': xform_validation_errored,
    }

    if isinstance(form, CareplanForm):
        context.update({
            'mode': form.mode,
            'fixed_questions': form.get_fixed_questions(),
            'custom_case_properties': [{'key': key, 'path': path} for key, path in form.custom_case_updates.items()],
            'case_preload': [{'key': key, 'path': path} for key, path in form.case_preload.items()],
        })
        return "app_manager/form_view_careplan.html", context
    else:
        context.update({
            'is_user_registration': is_user_registration,
            'show_custom_ref': toggle_enabled(toggles.APP_BUILDER_CUSTOM_PARENT_REF, request.user.username),
        })
        return "app_manager/form_view.html", context


def get_app_view_context(request, app):

    context = {
        'settings_layout': commcare_settings.LAYOUT[app.get_doc_type()],
        'settings_values': get_settings_values(app),
    }

    build_config = CommCareBuildConfig.fetch()
    version = app.application_version
    options = build_config.get_menu(version)
    if not request.user.is_superuser:
        options = [option for option in options if not option.superuser_only]
    options_labels = [option.get_label() for option in options]
    options_builds = [option.build.to_string() for option in options]

    (build_spec_setting,) = filter(
        lambda x: x['type'] == 'hq' and x['id'] == 'build_spec',
        [setting for section in context['settings_layout']
            for setting in section['settings']]
    )
    build_spec_setting['values'] = options_builds
    build_spec_setting['value_names'] = options_labels
    build_spec_setting['default'] = build_config.get_default(app.application_version).to_string()

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
        context.update({
            'multimedia': multimedia,
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


def get_apps_base_context(request, domain, app):

    lang, langs = get_langs(request, app)

    if getattr(request, 'couch_user', None):
        edit = (request.GET.get('edit', 'true') == 'true') and\
               (request.couch_user.can_edit_apps(domain) or request.user.is_superuser)
        timezone = report_utils.get_timezone(request.couch_user.user_id, domain)
    else:
        edit = False
        timezone = None

    if app:
        for _lang in app.langs:
            try:
                SuccessMessage(app.success_message.get(_lang, ''), '').check_message()
            except Exception as e:
                messages.error(request, "Your success message is malformed: %s is not a keyword" % e)

    return {
        'lang': lang,
        'langs': langs,
        'domain': domain,
        'edit': edit,
        'app': app,
        'URL_BASE': get_url_base(),
        'timezone': timezone,
    }


@cache_control(no_cache=True, no_store=True)
@login_and_domain_required
def paginate_releases(request, domain, app_id):
    limit = request.GET.get('limit', 10)
    start_build_param = request.GET.get('start_build')
    if start_build_param and json.loads(start_build_param):
        start_build = json.loads(start_build_param)
        assert isinstance(start_build, int)
    else:
        start_build = {}
    timezone = report_utils.get_timezone(request.couch_user.user_id, domain)
    saved_apps = get_db().view('app_manager/saved_app',
        startkey=[domain, app_id, start_build],
        endkey=[domain, app_id],
        descending=True,
        limit=limit,
        wrapper=lambda x: SavedAppBuild.wrap(x['value']).to_saved_build_json(timezone),
    ).all()
    for app in saved_apps:
        app['include_media'] = toggle_enabled(toggles.APP_BUILDER_INCLUDE_MULTIMEDIA_ODK, request.user.username)
    return json_response(saved_apps)


@login_and_domain_required
def release_manager(request, domain, app_id, template='app_manager/releases.html'):
    app = get_app(domain, app_id)
    latest_release = get_app(domain, app_id, latest=True)
    context = get_apps_base_context(request, domain, app)
    context['sms_contacts'] = get_sms_autocomplete_context(request, domain)['sms_contacts']

    context.update({
        'release_manager': True,
        'saved_apps': [],
        'latest_release': latest_release,
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
    if ajax:
        return json_response({'is_released': is_released})
    else:
        return HttpResponseRedirect(reverse('release_manager', args=[domain, app_id]))


def get_module_view_context_and_template(app, module):
    builder = ParentCasePropertyBuilder(
        app,
        defaults=('name', 'date-opened', 'status')
    )

    def get_parent_modules_and_save(case_type):
        parent_types = builder.get_parent_types(case_type)
        modules = app.modules
        # make sure all modules have unique ids
        if any(not mod.unique_id for mod in modules):
            for mod in modules:
                mod.get_or_create_unique_id()
            app.save()
        parent_module_ids = [mod.unique_id for mod in modules
                             if mod.case_type in parent_types]
        return [{
                    'unique_id': mod.unique_id,
                    'name': mod.name,
                    'is_parent': mod.unique_id in parent_module_ids,
                } for mod in app.modules if mod.case_type != case_type and mod.unique_id != module.unique_id]

    def get_sort_elements(details):
        return [prop.values() for prop in details.sort_elements]

    if isinstance(module, CareplanModule):
        return "app_manager/module_view_careplan.html", {
            'parent_modules': get_parent_modules_and_save(CAREPLAN_GOAL),
            'goal_case_properties': sorted(builder.get_properties(CAREPLAN_GOAL)),
            'task_case_properties': sorted(builder.get_properties(CAREPLAN_TASK)),
            "goal_sortElements": json.dumps(get_sort_elements(module.goal_details.short)),
            "task_sortElements": json.dumps(get_sort_elements(module.task_details.short)),
        }
    else:
        case_type = module.case_type
        return "app_manager/module_view.html", {
            'parent_modules': get_parent_modules_and_save(case_type),
            'case_properties': sorted(builder.get_properties(case_type)),
            "sortElements": json.dumps(get_sort_elements(module.case_details.short))
        }


@retry_resource(3)
def view_generic(req, domain, app_id=None, module_id=None, form_id=None, is_user_registration=False):
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
            if not app.user_registration.unique_id:
                # you have to do it this way because get_user_registration
                # changes app.user_registration.unique_id
                form = app.get_user_registration()
                app.save()
            else:
                form = app.get_user_registration()

        if module_id:
            module = app.get_module(module_id)
        if form_id:
            form = module.get_form(form_id)
    except IndexError:
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

    v2_app = app and app.application_version == APP_V2
    context.update({
        'show_care_plan': (v2_app
                           and not (app and app.has_careplan_module)
                           and toggle_enabled(toggles.APP_BUILDER_CAREPLAN, req.user.username)),
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
        context.update(form_context)
    elif module:
        template, module_context = get_module_view_context_and_template(app, module)
        context.update(module_context)
    else:
        template = "app_manager/app_view.html"
        if app:
            context.update(get_app_view_context(req, app))

    error = req.GET.get('error', '')

    context.update({
        'error':error,
        'app': app,
    })
    response = render(req, template, context)
    response.set_cookie('lang', _encode_if_unicode(context['lang']))
    return response

@login_and_domain_required
def get_commcare_version(request, app_id, app_version):
    options = CommCareBuildConfig.fetch().get_menu(app_version)
    return json_response(options)

@login_and_domain_required
def view_user_registration(request, domain, app_id):
    return view_generic(request, domain, app_id, is_user_registration=True)

@login_and_domain_required
def view_form(req, domain, app_id, module_id, form_id):
    return view_generic(req, domain, app_id, module_id, form_id)

@login_and_domain_required
def view_module(req, domain, app_id, module_id):
    return view_generic(req, domain, app_id, module_id)

@login_and_domain_required
def view_app(req, domain, app_id=None):
    # redirect old m=&f= urls
    module_id = req.GET.get('m', None)
    form_id = req.GET.get('f', None)
    if module_id or form_id:
        return back_to_main(req, domain, app_id=app_id, module_id=module_id,
                            form_id=form_id)

    return view_generic(req, domain, app_id)

@login_and_domain_required
def form_source(req, domain, app_id, module_id, form_id):
    return form_designer(req, domain, app_id, module_id, form_id)

@login_and_domain_required
def user_registration_source(req, domain, app_id):
    return form_designer(req, domain, app_id, is_user_registration=True)

@login_and_domain_required
def form_designer(req, domain, app_id, module_id=None, form_id=None,
                  is_user_registration=False):
    app = get_app(domain, app_id)

    if is_user_registration:
        form = app.get_user_registration()
    else:
        try:
            module = app.get_module(module_id)
        except IndexError:
            return bail(req, domain, app_id, not_found="module")
        try:
            form = module.get_form(form_id)
        except IndexError:
            return bail(req, domain, app_id, not_found="form")

    context = get_apps_base_context(req, domain, app)
    context.update(locals())
    context.update({
        'edit': True,
        'nav_form': form if not is_user_registration else '',
        'formdesigner': True,
        'multimedia_object_map': app.get_object_map()
    })
    return render(req, 'app_manager/form_designer.html', context)



@no_conflict_require_POST
@require_can_edit_apps
def new_app(req, domain):
    "Adds an app to the database"
    lang = req.COOKIES.get('lang') or 'en'
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
    elif module_type == 'careplan':
        validations = [
            (lambda a: a.application_version == APP_V1,
             _('Please upgrade you app to > 2.0 in order to add a Careplan module')),
            (lambda a: app.has_careplan_module,
             _('This application already has a Careplan module'))
        ]
        error = next((v[1] for v in validations if v[0](app)), None)
        if error:
            messages.warning(req, error)
            return back_to_main(req, domain, app_id=app.id)
        else:
            return _new_careplan_module(req, domain, app, name, lang)
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
    messages.warning(req, 'Care Plan modules are a work in progress!')
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
def delete_module(req, domain, app_id, module_id):
    "Deletes a module from an app"
    app = get_app(domain, app_id)
    record = app.delete_module(module_id)
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
def delete_form(req, domain, app_id, module_id, form_id):
    "Deletes a form from an app"
    app = get_app(domain, app_id)
    record = app.delete_form(module_id, form_id)
    messages.success(req,
        'You have deleted a form. <a href="%s" class="post-link">Undo</a>' % reverse('undo_delete_form', args=[domain, record.get_id]),
        extra_tags='html'
    )
    app.save()
    return back_to_main(req, domain, app_id=app_id, module_id=module_id)


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
    else:
        app.save()

    return back_to_main(req, domain, app_id=app_id, module_id=module_id,
                        form_id=form_id)


@no_conflict_require_POST
@require_can_edit_apps
def undo_delete_form(request, domain, record_id):
    record = DeleteFormRecord.get(record_id)
    record.undo()
    messages.success(request, 'Form successfully restored.')
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
        "case_type": None, "put_in_root": None,
        "name": None, "case_label": None, "referral_label": None,
        'media_image': None, 'media_audio': None,
        "case_list": ('case_list-show', 'case_list-label'),
        "task_list": ('task_list-show', 'task_list-label'),
        "parent_module": None,
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
    resp = {'update': {}}
    if should_edit("case_type"):
        case_type = req.POST.get("case_type", None)
        if is_valid_case_type(case_type):
            # todo: something better than nothing when invalid
            module["case_type"] = case_type
            for cp_mod in (mod for mod in app.modules if isinstance(mod, CareplanModule)):
                if cp_mod.unique_id != module.unique_id and cp_mod.parent_select.module_id == module.unique_id:
                    cp_mod.case_type = case_type
        else:
            return HttpResponseBadRequest("case type is improperly formatted")
    if should_edit("put_in_root"):
        module["put_in_root"] = json.loads(req.POST.get("put_in_root"))
    if should_edit("parent_module"):
        parent_module = req.POST.get("parent_module")
        module.parent_select.module_id = parent_module
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

    _handle_media_edits(req, module, should_edit, resp)

    app.save(resp)
    resp['case_list-show'] = module.requires_case_details()
    return HttpResponse(json.dumps(resp))

@no_conflict_require_POST
@require_can_edit_apps
def edit_module_detail_screens(req, domain, app_id, module_id):
    """
    Called to over write entire detail screens at a time

    """
    params = json_request(req.POST)
    detail_type = params.get('type')
    screens = params.get('screens')
    parent_select = params.get('parent_select')
    sort_elements = screens['sort_elements']

    if not screens:
        return HttpResponseBadRequest("Requires JSON encoded param 'screens'")

    app = get_app(domain, app_id)
    module = app.get_module(module_id)

    if detail_type == 'case':
        detail = module.case_details
    elif detail_type == CAREPLAN_GOAL:
        detail = module.goal_details
    elif detail_type == CAREPLAN_TASK:
        detail = module.task_details
    else:
        return HttpResponseBadRequest("Unknown detail type '%s'" % detail_type)

    detail.short.columns = map(DetailColumn.wrap, screens['short'])
    detail.long.columns = map(DetailColumn.wrap, screens['long'])

    detail.short.sort_elements = []
    for sort_element in sort_elements:
        item = SortElement()
        item.field = sort_element['field']
        item.type = sort_element['type']
        item.direction = sort_element['direction']
        detail.short.sort_elements.append(item)

    module.parent_select = ParentSelect.wrap(parent_select)
    resp = {}
    app.save(resp)
    return json_response(resp)


def _handle_media_edits(request, item, should_edit, resp):
    if not resp.has_key('corrections'):
        resp['corrections'] = {}
    for attribute in ('media_image', 'media_audio'):
        if should_edit(attribute):
            val = request.POST.get(attribute)
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

    _handle_media_edits(req, form, should_edit, resp)

    app.save(resp)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(req, domain, app_id=app_id, unique_form_id=unique_form_id)


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
    except XFormError as e:
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
        settings = json.loads(request.raw_post_data)
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
    o = json.loads(request.raw_post_data)
    app = get_app(domain, app_id)
    langs = o['langs']
    rename = o['rename']
    build = o['build']

    try:
        assert set(rename.keys()).issubset(app.langs)
        assert set(rename.values()).issubset(langs)
        # assert that there are no repeats in the values of rename
        assert len(set(rename.values())) == len(rename.values())
        # assert that no lang is renamed to an already existing lang
        for old, new in rename.items():
            if old != new:
                assert(new not in app.langs)
        # assert that the build langs are in the correct order
        assert sorted(build, key=lambda lang: langs.index(lang)) == build
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
    params  = json_request(request.POST)
    lang    = params.get('lang')
    translations = params.get('translations')
    #    key     = params.get('key')
    #    value   = params.get('value')
    app = get_app(domain, app_id)
    app.set_translations(lang, translations)
    response = {}
    app.save(response)
    return json_response(response)

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
        hq_settings = json.loads(request.raw_post_data)['hq']
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
        'translation_strategy'
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
        ('manage_urls', None),
        ('name', None),
        ('platform', None),
        ('recipients', None),
        ('show_user_registration', None),
        ('text_input', None),
        ('use_custom_suite', None),
        ('secure_submissions', None),
        ('translation_strategy', None),
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
    except RearrangeError:
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
        report_utils.get_timezone(req.couch_user.user_id, domain)
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
    except KeyError:
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

@safe_download
def download_index(req, domain, app_id, template="app_manager/download_index.html"):
    """
    A landing page, mostly for debugging, that has links the jad and jar as well as
    all the resource files that will end up zipped into the jar.

    """
    files = []
    if req.app.copy_of:
        files = [(path[len('files/'):], req.app.fetch_attachment(path)) for path in req.app._attachments if path.startswith('files/')]
    else:
        try:
            files = sorted(req.app.create_all_files().items())
        except Exception:
            messages.error(req, _(
                "We were unable to get your files "
                "because your Application has errors. "
                "Please click <strong>Make New Version</strong> "
                "under <strong>Deploy</strong> "
                "for feedback on how to fix these errors."
            ), extra_tags='html')
    return render(req, template, {
        'app': req.app,
        'files': files,
    })

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
                notify_exception(req, 'Build resource not found')
                raise Http404()
        callback, callback_args, callback_kwargs = RegexURLResolver(r'^', 'corehq.apps.app_manager.download_urls').resolve(path)
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
    except IndexError:
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

def emulator_page(req, domain, app_id, template):
    copied_app = app = get_app(domain, app_id)
    if app.copy_of:
        app = get_app(domain, app.copy_of)

    # Coupled URL -- Sorry!
    build_path = "/builds/{version}/{build_number}/Generic/WebDemo/".format(
        **copied_app.get_preview_build()._doc
    )
    return render(req, template, {
        'domain': domain,
        'app': app,
        'build_path': build_path,
        'url_base': get_url_base()
    })


@login_and_domain_required
def emulator(req, domain, app_id, template="app_manager/emulator.html"):
    return emulator_page(req, domain, app_id, template)


def emulator_handler(req, domain, app_id):
    exchange = req.GET.get("exchange", '')
    if exchange:
        return emulator_page(req, domain, app_id, template="app_manager/exchange_emulator.html")
    else:
        return emulator(req, domain, app_id)

def emulator_commcare_jar(req, domain, app_id):
    response = HttpResponse(
        get_app(domain, app_id).fetch_emulator_commcare_jar()
    )
    response['Content-Type'] = "application/java-archive"
    return response

@login_and_domain_required
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

@login_and_domain_required
def app_summary(request, domain, app_id):
    return summary(request, domain, app_id, should_edit=True)

def app_summary_from_exchange(request, domain, app_id):
    dom = Domain.get_by_name(domain)
    if dom.is_snapshot:
        return summary(request, domain, app_id, should_edit=False)
    else:
        return HttpResponseForbidden()

def summary(request, domain, app_id, should_edit=True):
    app = get_app(domain, app_id)
    if app.doc_type == 'RemoteApp':
        raise Http404()
    context = get_apps_base_context(request, domain, app)
    langs = context['langs']

    modules = []

    for module in app.get_modules():
        forms = []
        for form in module.get_forms():
            questions, messages = _questions_for_form(request, form, langs)
            forms.append({'name': _find_name(form.name, langs),
                          'questions': questions,
                          'messages': dict(messages)})

        modules.append({'name': _find_name(module.name, langs), 'forms': forms})

    context['modules'] = modules
    context['summary'] = True

    if should_edit:
        return render(request, "app_manager/summary.html", context)
    else:
        return render(request, "app_manager/exchange_summary.html", context)

@login_and_domain_required
def download_translations(request, domain, app_id):
    app = get_app(domain, app_id)
    properties = tuple(["property"] + app.langs + ["default"])
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
    all_prop_trans = dict(st_trans.DEFAULT + st_trans.CC_DEFAULT + st_trans.CCODK_DEFAULT + st_trans.ODKCOLLECT_DEFAULT)
    all_prop_trans = dict((k.lower(), v) for k, v in all_prop_trans.iteritems())
    rows.extend([[t] for t in sorted(all_prop_trans.keys()) if t not in [k.lower() for k in row_dict]])

    def fillrow(row):
        num_to_fill = len(properties) - len(row)
        row.extend(["" for i in range(num_to_fill)] if num_to_fill > 0 else [])
        return row

    def add_default(row):
        row[-1] = all_prop_trans.get(row[0].lower(), "")
        return row

    rows = [add_default(fillrow(row)) for row in rows]

    data = (("translations", tuple(rows)),)
    export_raw(headers, data, temp)
    return export_response(temp, Format.XLS_2007, "translations")

@no_conflict_require_POST
@require_can_edit_apps
@get_file("file")
def upload_translations(request, domain, app_id):
    success = False
    try:
        workbook = WorkbookJSONReader(request.file)
        translations = workbook.get_worksheet(title='translations')

        app = get_app(domain, app_id)
        trans_dict = defaultdict(dict)
        for row in translations:
            for lang in app.langs:
                if row.get(lang):
                    trans_dict[lang].update({row["property"]: row[lang]})

        app.translations = dict(trans_dict)
        app.save()
        success = True
    except Exception:
        notify_exception(request, 'Bulk Upload Translations Error')
        messages.error(request, _("Something went wrong! Update failed. We're looking into it"))

    if success:
        messages.success(request, _("UI Translations Updated!"))

    return HttpResponseRedirect(reverse('app_languages', args=[domain, app_id]))
