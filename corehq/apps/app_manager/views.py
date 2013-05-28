from StringIO import StringIO
import functools
import logging
from diff_match_patch import diff_match_patch
from django.core.cache import cache
from django.template.loader import render_to_string
import hashlib
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from corehq.apps.app_manager.const import APP_V1
from corehq.apps.app_manager.success_message import SuccessMessage
from corehq.apps.app_manager.util import is_valid_case_type
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views import DomainViewMixin
from couchexport.export import FormattedRow
from couchexport.models import Format
from couchexport.writers import Excel2007ExportWriter
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.resource_conflict import retry_resource
from django.utils import html
from django.utils.http import urlencode as django_urlencode
import os
import re

from couchdbkit.exceptions import ResourceConflict
from django.http import HttpResponse, Http404, HttpResponseBadRequest, HttpResponseForbidden
from unidecode import unidecode
from corehq.apps.app_manager.xform import XFormError, XFormValidationError, CaseError,\
    XForm, parse_xml
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions, CommCareUser
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.cache import make_template_fragment_key
from dimagi.utils.logging import notify_exception
from dimagi.utils.subprocess_timeout import ProcessTimedOut

from dimagi.utils.web import json_response, json_request

from corehq.apps.app_manager.forms import NewXFormForm, NewModuleForm
from corehq.apps.reports import util as report_utils

from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest

from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse, RegexURLResolver
from django.shortcuts import render

from corehq.apps.app_manager.models import Application, get_app, DetailColumn, Form, FormActions,\
    AppError, load_case_reserved_words, ApplicationBase, DeleteFormRecord, DeleteModuleRecord, DeleteApplicationRecord, EXAMPLE_DOMAIN, str_to_cls, validate_lang, SavedAppBuild, load_commcare_settings_layout

from corehq.apps.app_manager.models import DETAIL_TYPES, import_app as import_app_util
from django.utils.http import urlencode

from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from dimagi.utils.web import get_url_base

import json
from collections import defaultdict
from couchdbkit.resource import ResourceNotFound
from corehq.apps.app_manager.decorators import safe_download
from xml.dom.minidom import parseString

try:
    from lxml.etree import XMLSyntaxError
except ImportError:
    logging.error("lxml not installed! apps won't work properly!!")
from django.contrib import messages

require_can_edit_apps = require_permission(Permissions.edit_apps)

def set_file_download(response, filename):
    response["Content-Disposition"] = "attachment; filename=%s" % filename

def _encode_if_unicode(s):
    return s.encode('utf-8') if isinstance(s, unicode) else s

CASE_TYPE_CONFLICT_MSG = "Warning: The form's new module has a different case type from the old module.<br />" + \
                             "Make sure all case properties you are loading are available in the new case type"


class ApplicationViewMixin(DomainViewMixin):
    """
        Paving the way for class-based views in app manager. Yo yo yo.
    """

    @property
    @memoized
    def app_id(self):
        return self.args[1] if len(self.args) > 1 else self.kwargs.get('app_id')

    @property
    @memoized
    def app(self):
        try:
            # if get_app is mainly used for views, maybe it should be a classmethod of this mixin? todo
            return get_app(self.domain, self.app_id)
        except Exception:
            pass
        return None


@login_and_domain_required
def back_to_main(req, domain, app_id=None, module_id=None, form_id=None, unique_form_id=None, edit=True, error='', page=None, **kwargs):
    """
    returns an HttpResponseRedirect back to the main page for the App Manager app
    with the correct GET parameters.

    This is meant to be used by views that process a POST request, which then redirect to the
    main page. The idiom for calling back_to_main used in this file is
        return back_to_main(**locals())
    which harvests the values for req, domain, app_id, module_id form_id, edit, and error from
    the local namespace.

    """
    params = {}
    if edit:
        params['edit'] = 'true'
    if error:
        params['error'] = error

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
    form = app.get_module(module_id).get_form(form_id)
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
def import_app(req, domain, template="app_manager/import_app.html"):
    if req.method == "POST":
        _clear_app_cache(req, domain)
        name = req.POST.get('name')
        try:
            source = req.POST.get('source')
            source = json.loads(source)
            assert(source is not None)
            app = import_app_util(source, domain, name=name)
        except Exception:
            app_id = req.POST.get('app_id')
            def validate_source_domain(src_dom):
                if src_dom != EXAMPLE_DOMAIN and not req.couch_user.can_edit_apps(domain=domain):
                    return HttpResponseForbidden()
            app = import_app_util(app_id, domain, name=name, validate_source_domain=validate_source_domain)

        app_id = app._id
        return back_to_main(**locals())
    else:
        app_id = req.GET.get('app')
        redirect_domain = req.GET.get('domain') or None
        if redirect_domain is not None:
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
                return HttpResponseRedirect(req.META['HTTP_REFERER'])

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

@require_can_edit_apps
@require_POST
def import_factory_app(req, domain):
    factory_app = get_app('factory', req.POST['app_id'])
    source = factory_app.export_json(dump_json=False)
    name = req.POST.get('name')
    if name:
        source['name'] = name
    cls = str_to_cls[source['doc_type']]
    app = cls.from_source(source, domain)
    app.save()
    app_id = app._id
    return back_to_main(**locals())

@require_can_edit_apps
@require_POST
def import_factory_module(req, domain, app_id):
    fapp_id, fmodule_id = req.POST['app_module_id'].split('/')
    fapp = get_app('factory', fapp_id)
    fmodule = fapp.get_module(fmodule_id)
    app = get_app(domain, app_id)
    source = fmodule.export_json(dump_json=False)
    app.new_module_from_source(source)
    app.save()
    return back_to_main(**locals())

@require_can_edit_apps
@require_POST
def import_factory_form(req, domain, app_id, module_id):
    fapp_id, fmodule_id, fform_id = req.POST['app_module_form_id'].split('/')
    fapp = get_app('factory', fapp_id)
    fform = fapp.get_module(fmodule_id).get_form(fform_id)
    source = fform.export_json(dump_json=False)
    app = get_app(domain, app_id)
    app.new_form_from_source(module_id, source)
    app.save()
    return back_to_main(**locals())

def default(req, domain):
    """
    Handles a url that does not include an app_id.
    Currently the logic is taken care of by view_app,
    but this view exists so that there's something to
    reverse() to. (I guess I should use url(..., name="default")
    in url.py instead?)


    """
    return view_app(req, domain)


def get_form_view_context(request, form, langs, is_user_registration, messages=messages):
    xform_questions = []
    xform = None
    form_errors = []

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
            xform_questions = xform.get_questions(langs)
        except XMLSyntaxError as e:
            form_errors.append("Syntax Error: %s" % e)
        except AppError as e:
            form_errors.append("Error in application: %s" % e)
        except XFormValidationError as e:

            # Don't display the first two lines which say "Parsing form..." and 'Title: "{form_name}"'
            #
            # ... and if possible split the third line that looks like e.g. "org.javarosa.xform.parse.XFormParseException: Select question has no choices"
            # and just return the undecorated string
            #
            # ... unless the first line says
            message_lines = unicode(e).split('\n')[2:]
            if len(message_lines) > 0 and ':' in message_lines[0] and 'XPath Dependency Cycle' not in unicode(e):
                message = ' '.join(message_lines[0].split(':')[1:])
            else:
                message = '\n'.join(message_lines)
                
            message = "Validation Error: " + message
            form_errors.append((html.escape(message).replace('\n', '<br/>'), {'extra_tags': 'html'}))

        except XFormError as e:
            form_errors.append("Error in form: %s" % e)
        # any other kind of error should fail hard, but for now there are too many for that to be practical
        except Exception as e:
            if settings.DEBUG:
                raise
            logging.exception(e)
            form_errors.append("Unexpected System Error: %s" % e)

        try:
            form_action_errors = form.validate_for_build()
            if not form_action_errors:
                xform.add_case_and_meta(form)
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

    return {
        'nav_form': form if not is_user_registration else '',
        'xform_languages': languages,
        "xform_questions": xform_questions,
        'form_actions': form.actions.to_json(),
        'case_reserved_words_json': load_case_reserved_words(),
        'is_user_registration': is_user_registration,
        'module_case_types': [{'module_name': module.name.get('en'), 'case_type': module.case_type} for module in form.get_app().modules if module.case_type] if not is_user_registration else None,
        'form_errors': form_errors,
    }


def get_app_view_context(request, app):
    try:
        profile = app.profile
    except AttributeError:
        profile = {}
    hq_settings = dict([
        (attr, app[attr])
        for attr in app.properties() if not hasattr(app[attr], 'pop')
    ])
    if hasattr(app, 'custom_suite'):
        hq_settings.update({'custom_suite': app.custom_suite})
    context = {
        'settings_layout': load_commcare_settings_layout(app.get_doc_type()),
        'settings_values': {
            'properties': profile.get('properties', {}),
            'features': profile.get('features', {}),
            'hq': hq_settings,
            '$parent': {
                'doc_type': app.get_doc_type()
            }
        }
    }
    context['settings_values']['hq']['build_spec'] = app.build_spec.to_string()


    commcare_build_options = {}
    build_config = CommCareBuildConfig.fetch()
    for version in [app.application_version]:
        options = build_config.get_menu(version)
        options_labels = list()
        options_builds = list()
        for option in options:
            options_labels.append(option.get_label())
            options_builds.append(option.build.to_string())
            commcare_build_options[version] = {"options" : options, "labels" : options_labels, "builds" : options_builds}

    (build_spec_setting,) = filter(
        lambda x: x['type'] == 'hq' and x['id'] == 'build_spec',
        [setting for section in context['settings_layout']
            for setting in section['settings']]
    )
    build_spec_setting['values'] = options_builds
    build_spec_setting['value_names'] = options_labels
    build_spec_setting['default'] = build_config.get_default(app.application_version).to_string()

    app_build_spec_string = app.build_spec.to_string()
    app_build_spec_label = app.build_spec.get_label()

    context.update({
        "commcare_build_options" : commcare_build_options,
        "app_build_spec_string" : app_build_spec_string,  # todo: remove
        "app_build_spec_label" : app_build_spec_label,  # todo: remove
        "app_version" : app.application_version,  # todo: remove
    })

    if app.get_doc_type() == 'Application':
        try:
            # todo remove get_media_references
            multimedia = app.get_media_references()
        except ProcessTimedOut as e:
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
            ApplicationsTab.view,
            is_active,
            request.couch_user.get_id
        ])
        cache.delete(key)


def get_apps_base_context(request, domain, app):

    applications = ApplicationBase.view('app_manager/applications_brief',
        startkey=[domain],
        endkey=[domain, {}],
        stale=settings.COUCH_STALE_QUERY,
    ).all()

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
        'applications': applications,
        'app': app,
        'URL_BASE': get_url_base(),
        'timezone': timezone,
    }

@cache_control(no_cache=True, no_store=True)
@login_and_domain_required
def paginate_releases(request, domain, app_id):
    limit = request.GET.get('limit', 10)
    start_build = json.loads(request.GET.get('start_build'))
    if start_build:
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
    return json_response(saved_apps)

@login_and_domain_required
def release_manager(request, domain, app_id, template='app_manager/releases.html'):
    app = get_app(domain, app_id)
    latest_release = get_app(domain, app_id, latest=True)
    context = get_apps_base_context(request, domain, app)

    saved_apps = []

    users_cannot_share = CommCareUser.cannot_share(domain)
    context.update({
        'release_manager': True,
        'saved_apps': saved_apps,
        'latest_release': latest_release,
        'users_cannot_share': users_cannot_share,
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

@require_POST
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

    base_context = get_apps_base_context(req, domain, app)
    edit = base_context['edit']
    applications = base_context['applications']
    if not app and applications:
        app_id = applications[0]['id']
        del edit
        return back_to_main(**locals())
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

    case_properties = set()
    if module:
        @memoized
        def get_properties(case_type,
                defaults=("name", "date-opened", "status"),
                already_visited=()):

            if case_type in already_visited:
                return ()

            get_properties_recursive = functools.partial(
                get_properties,
                already_visited=already_visited + (case_type,)
            )

            case_properties = set(defaults)
            parent_types = set()

            for module in app.get_modules():
                for form in module.get_forms():
                    if module.case_type == case_type:
                        case_properties.update(
                            form.actions.update_case.update.keys()
                        )
                    for subcase in form.actions.subcases:
                        if subcase.case_type == case_type:
                            case_properties.update(
                                subcase.case_properties.keys()
                            )
                            parent_types.add(module.case_type)

            for parent_type in parent_types:
                for property in get_properties_recursive(parent_type):
                    case_properties.add('parent/%s' % property)

            return case_properties

        case_properties = list(get_properties(module.case_type))

    context = {
        'domain': domain,
        'applications': applications,

        'app': app,
        'module': module,
        'form': form,

        'case_properties': case_properties,

        'new_module_form': NewModuleForm(),
        'new_xform_form': NewXFormForm(),

        'show_secret_settings': req.GET.get('secret', False)
    }
    context.update(base_context)
    if app and not module and hasattr(app, 'translations'):
        context.update({"translations": app.translations.get(context['lang'], {})})

    if form:
        template = "app_manager/form_view.html"
        context.update(get_form_view_context(req, form, context['langs'], is_user_registration))
    elif module:
        template = "app_manager/module_view.html"
    else:
        template = "app_manager/app_view.html"
        if app:
            context.update(get_app_view_context(req, app))

    error = req.GET.get('error', '')

    force_edit = False
    if (not context['applications']) or (app and app.get_doc_type() == "Application" and not app.modules):
        edit = True
        force_edit = True
    context.update({
        'force_edit': force_edit,
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
        return back_to_main(**locals())
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
    })
    return render(req, 'app_manager/form_designer.html', context)



@require_POST
@require_can_edit_apps
def new_app(req, domain):
    "Adds an app to the database"
    lang = req.COOKIES.get('lang') or 'en'
    type = req.POST["type"]
    application_version = req.POST.get('application_version', APP_V1)
    cls = str_to_cls[type]
    if cls == Application:
        app = cls.new_app(domain, "Untitled Application", lang=lang, application_version=application_version)
        app.new_module("Untitled Module", lang)
        app.new_form(0, "Untitled Form", lang)
    else:
        app = cls.new_app(domain, "Untitled Application", lang=lang)
    app.save()
    _clear_app_cache(req, domain)
    app_id = app.id

    return back_to_main(**locals())

@require_POST
@require_can_edit_apps
def new_module(req, domain, app_id):
    "Adds a module to an app"
    app = get_app(domain, app_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    name = req.POST.get('name')
    module = app.new_module(name, lang)
    module_id = module.id
    app.new_form(module_id, "Untitled Form", lang)
    app.save()
    response = back_to_main(**locals())
    response.set_cookie('suppress_build_errors', 'yes')
    return response

@require_POST
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
    response = back_to_main(**locals())
    response.set_cookie('suppress_build_errors', 'yes')
    return response

@require_POST
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
    del app_id
    return back_to_main(**locals())

@require_POST
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

@require_POST
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
    del module_id
    return back_to_main(**locals())

@require_POST
@require_can_edit_apps
def undo_delete_module(request, domain, record_id):
    record = DeleteModuleRecord.get(record_id)
    record.undo()
    messages.success(request, 'Module successfully restored.')
    return back_to_main(request, domain, app_id=record.app_id, module_id=record.module_id)


@require_POST
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
    del form_id
    del record
    return back_to_main(**locals())

@require_POST
@require_can_edit_apps
def undo_delete_form(request, domain, record_id):
    record = DeleteFormRecord.get(record_id)
    record.undo()
    messages.success(request, 'Form successfully restored.')
    return back_to_main(request, domain, app_id=record.app_id, module_id=record.module_id, form_id=record.form_id)

@require_POST
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
        else:
            resp['update'].update({'#case_type': module['case_type']})
    if should_edit("put_in_root"):
        module["put_in_root"] = json.loads(req.POST.get("put_in_root"))
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

@require_POST
@require_can_edit_apps
def edit_module_detail_screens(req, domain, app_id, module_id):
    """
    Called to over write entire detail screens at a time

    """

    params = json_request(req.POST)
    screens = params.get('screens')

    if not screens:
        return HttpResponseBadRequest("Requires JSON encoded param 'screens'")
    for detail_type in screens:
        if detail_type not in DETAIL_TYPES:
            return HttpResponseBadRequest("All detail types must be in %r" % DETAIL_TYPES)

    app = get_app(domain, app_id)
    module = app.get_module(module_id)

    for detail_type in screens:
        module.get_detail(detail_type).columns = [DetailColumn.wrap(c) for c in screens[detail_type]]
    resp = {}
    app.save(resp)
    return json_response(resp)

@require_POST
@require_can_edit_apps
def edit_module_detail(req, domain, app_id, module_id):
    """
    Called to add a new module detail column or edit an existing one

    """
    column_id = int(req.POST.get('index', -1))
    detail_type = req.POST.get('detail_type', '')
    assert(detail_type in DETAIL_TYPES)

    column = dict((key, req.POST.get(key)) for key in (
        'header', 'model', 'field', 'format',
        'enum', 'late_flag', 'advanced'
        ))
    app = get_app(domain, app_id)
    module = app.get_module(module_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    ajax = (column_id != -1) # edits are ajax, adds are not

    resp = {}

    def _enum_to_dict(enum):
        if not enum:
            return {}
        answ = {}
        for s in enum.split(','):
            key, val = (x.strip() for x in s.strip().split('='))
            answ[key] = {}
            answ[key][lang] = val
        return answ

    column['enum'] = _enum_to_dict(column['enum'])
    column['header'] = {lang: column['header']}
    column = DetailColumn.wrap(column)
    detail = app.get_module(module_id).get_detail(detail_type)

    if(column_id == -1):
        detail.append_column(column)
    else:
        detail.update_column(column_id, column)
    app.save(resp)
    column = detail.get_column(column_id)
    if(ajax):
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(**locals())

@require_POST
@require_can_edit_apps
def delete_module_detail(req, domain, app_id, module_id):
    """
    Called when a module detail column is to be deleted

    """
    column_id = int(req.POST['index'])
    detail_type = req.POST['detail_type']
    app = get_app(domain, app_id)
    module = app.get_module(module_id)
    module.get_detail(detail_type).delete_column(column_id)
    resp = {}
    app.save(resp)
    return HttpResponse(json.dumps(resp))
    #return back_to_main(**locals())

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

def _save_xform(app, form, xml):
    try:
        xform = XForm(xml)
    except XFormError:
        pass
    else:
        duplicates = app.get_xmlns_map()[xform.data_node.tag_xmlns]
        for duplicate in duplicates:
            if form == duplicate:
                continue
            else:
                data = xform.data_node.render()
                xmlns = "http://openrosa.org/formdesigner/%s" % form.get_unique_id()
                data = data.replace(xform.data_node.tag_xmlns, xmlns, 1)
                xform.instance_node.remove(xform.data_node.xml)
                xform.instance_node.append(parse_xml(data))
                xml = xform.render()
                break
    form.source = xml

@require_POST
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
    _save_xform(app, form, xform)
    response_json = {
        'status': 'ok',
        'sha1': hashlib.sha1(form.source.encode('utf-8')).hexdigest()
    }
    app.save(response_json)
    return json_response(response_json)

@require_POST
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

    if should_edit("requires"):
        requires = req.POST['requires']
        form.set_requires(requires)
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
                _save_xform(app, form, xform)
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
        return back_to_main(**locals())

@require_POST
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

@require_POST
@require_can_edit_apps
def edit_form_actions(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    form.actions = FormActions.wrap(json.loads(req.POST['actions']))
    form.requires = req.POST.get('requires', form.requires)
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


@require_POST
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

@require_POST
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


@require_POST
@require_can_edit_apps
def edit_app_lang(req, domain, app_id):
    """
    DEPRECATED
    Called when an existing language (such as 'zh') is changed (e.g. to 'zh-cn')
    or when a language is to be added.

    """
    lang = req.POST['lang']
    lang_id = int(req.POST.get('index', -1))
    app = get_app(domain, app_id)
    if lang_id == -1:
        if lang in app.langs:
            messages.error(req, "Language %s already exists" % lang)
        else:
            try:
                validate_lang(lang)
            except ValueError as e:
                messages.error(req, unicode(e))
            else:
                app.langs.append(lang)
                app.save()
    else:
        try:
            app.rename_lang(app.langs[lang_id], lang)
        except AppError as e:
            messages.error(req, unicode(e))
        except ValueError as e:
            messages.error(req, unicode(e))
        else:
            app.save()

    return back_to_main(**locals())

@require_POST
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
@require_POST
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

@require_POST
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
    return back_to_main(**locals())

@require_POST
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
    )
    for attribute, transformation in easy_attrs:
        if should_edit(attribute):
            value = hq_settings[attribute]
            if transformation:
                value = transformation(value)
            setattr(app, attribute, value)

    if should_edit("name"):
        resp['update'].update({'.variable-app_name': hq_settings['name']})

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


@require_POST
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


    if   "forms" == key:
        to_module_id = int(req.POST['to_module_id'])
        from_module_id = int(req.POST['from_module_id'])
        if app.rearrange_forms(to_module_id, from_module_id, i, j) == 'case type conflict':
            messages.warning(req, CASE_TYPE_CONFLICT_MSG,  extra_tags="html")
    elif "modules" == key:
        app.rearrange_modules(i, j)
    elif "detail" == key:
        module_id = int(req.POST['module_id'])
        app.rearrange_detail_columns(module_id, req.POST['detail_type'], i, j)
    elif "langs" == key:
        app.rearrange_langs(i, j)
    app.save(resp)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(**locals())


# The following three functions deal with
# Saving multiple versions of the same app
# i.e. "making builds"

@require_POST
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
            copy = app.save_copy(
                comment=comment,
                user_id=req.couch_user.get_id,
                previous_version=app.get_latest_app(released_only=False)
            )
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

def validate_form_for_build(request, domain, app_id, unique_form_id):
    app = get_app(domain, app_id)
    try:
        form = app.get_form(unique_form_id)
    except KeyError:
        # this can happen if you delete the form from another page
        raise Http404()
    errors = form.validate_for_build()
    lang, langs = get_langs(request, app)
    return json_response({
        "error_html": render_to_string('app_manager/partials/build_errors.html', {
            'app': app,
            'form': form,
            'build_errors': errors,
            'not_actual_build': True,
            'domain': domain,
            'langs': langs,
            'lang': lang
        }),
    })
    
@require_POST
@require_can_edit_apps
def revert_to_copy(req, domain, app_id):
    """
    Copies a saved doc back to the original.
    See VersionedDoc.revert_to_copy

    """
    app = get_app(domain, app_id)
    copy = get_app(domain, req.POST['saved_app'])
    app = app.revert_to_copy(copy)
    messages.success(req, "Successfully reverted to version %s, now at version %s" % (copy.version, app.version))
    return back_to_main(**locals())

@require_POST
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
    }
    try:
        response = HttpResponse(mimetype=mimetype_map[path.split('.')[-1]])
    except KeyError:
        response = HttpResponse()
    try:
        response.write(req.app.fetch_attachment('files/%s' % path))
        assert req.app.copy_of
        return response
    except (ResourceNotFound, AssertionError):
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

def odk_install(req, domain, app_id):
    return render(req, "app_manager/odk_install.html",
            {"domain": domain, "app": get_app(domain, app_id)})

def odk_qr_code(req, domain, app_id):
    qr_code = get_app(domain, app_id).get_odk_qr_code()
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
        return back_to_main(**locals())
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
        return back_to_main(**locals())
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

    context = get_form_view_context(request, form, langs, None, messages=m)
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
    app = Application.get(app_id)
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
