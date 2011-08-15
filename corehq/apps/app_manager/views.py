import logging

from couchdbkit.exceptions import ResourceConflict
from django.http import HttpResponse, Http404, HttpResponseBadRequest, HttpResponseForbidden
from unidecode import unidecode
from corehq.apps.app_manager.xform import XFormError, XFormValidationError, CaseError,\
    XForm
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.apps.sms.views import get_sms_autocomplete_context
from corehq.apps.translations.models import TranslationMixin
from corehq.apps.users.models import DomainMembership, require_permission, Permissions
import current_builds
from dimagi.utils.web import render_to_response, json_response, json_request

from corehq.apps.app_manager.forms import NewXFormForm, NewAppForm, NewModuleForm

from corehq.apps.domain.decorators import login_and_domain_required

from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse, resolve
from corehq.apps.app_manager.models import RemoteApp, Application, VersionedDoc, get_app, DetailColumn, Form, FormAction, FormActionCondition, FormActions,\
    BuildErrors, AppError, load_case_reserved_words, ApplicationBase

from corehq.apps.app_manager.models import DETAIL_TYPES
from django.utils.http import urlencode

from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from dimagi.utils.web import get_url_base

import json
from dimagi.utils.make_uuid import random_hex
from utilities.profile import profile
import urllib
import urlparse
from collections import defaultdict
from dimagi.utils.couch.database import get_db
from couchdbkit.resource import ResourceNotFound
from corehq.apps.app_manager.decorators import safe_download
from . import fixtures
from django.utils.datastructures import SortedDict

try:
    from lxml.etree import XMLSyntaxError
except ImportError:
    logging.error("lxml not installed! apps won't work properly!!")
from django.contrib import messages

_str_to_cls = {"Application":Application, "RemoteApp":RemoteApp}

require_edit_apps = require_permission(Permissions.EDIT_APPS)

def _encode_if_unicode(s):
    return s.encode('utf-8') if isinstance(s, unicode) else s
@login_and_domain_required
def back_to_main(req, domain, app_id='', module_id='', form_id='', edit=True, error='', **kwargs):
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
    if app_id:
        args.append(app_id)
        if module_id:
            args.append(module_id)
            if form_id:
                args.append(form_id)
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

def _get_xform_contents(request, app, form):
    download = json.loads(request.GET.get('download', 'false'))
    lang = request.COOKIES.get('lang', app.langs[0])
    contents = form.contents
    if download:
        response = HttpResponse(contents)
        response['Content-Type'] = "application/xml"
        for lc in [lang] + app.langs:
            if lc in form.name:
                response["Content-Disposition"] = "attachment; filename=%s.xml" % unidecode(form.name[lc])
                break
        return response
    else:
        return json_response(contents)

@login_and_domain_required
def get_xform_contents(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    return _get_xform_contents(req, app, form)
    
@login_and_domain_required
def get_user_registration_contents(req, domain, app_id):
    app = get_app(domain, app_id)
    form = app.get_user_registration()
    return _get_xform_contents(req, app, form)

def xform_display(req, domain, form_unique_id):
    form, app = Form.get_form(form_unique_id, and_app=True)
    if domain != app.domain: raise Http404
    langs = [req.GET.get('lang')] + app.langs

    questions = form.get_questions(langs)

    return HttpResponse(json.dumps(questions))

@login_and_domain_required
def form_casexml(req, domain, form_unique_id):
    form, app = Form.get_form(form_unique_id, and_app=True)
    if domain != app.domain: raise Http404
    return HttpResponse(form.create_casexml())

@login_and_domain_required
def app_source(req, domain, app_id):
    app = get_app(domain, app_id)
    return HttpResponse(app.export_json())

EXAMPLE_DOMAIN = 'example'

def _get_or_create_app(app_id):
    if app_id == "example--hello-world":
        try:
            app = Application.get(app_id)
        except ResourceNotFound:
            app = Application.wrap(fixtures.hello_world_example)
            app._id = app_id
            app.domain = EXAMPLE_DOMAIN
            app.save()
            return _get_or_create_app(app_id)
        return app
    else:
        return VersionedDoc.get(app_id)

@login_and_domain_required
def import_app(req, domain, template="app_manager/import_app.html"):
    if req.method == "POST":
        name = req.POST.get('name')
        try:
            source = req.POST.get('source')
            source = json.loads(source)
            assert(source is not None)
        except Exception:
            app_id = req.POST.get('app_id')
            source = _get_or_create_app(app_id)
            src_dom = source['domain']
            source = source.export_json()
            source = json.loads(source)
            if src_dom != EXAMPLE_DOMAIN and not req.couch_user.has_permission(src_dom, Permissions.EDIT_APPS):
                return HttpResponseForbidden()
        try: del source['_attachments']
        except Exception: pass
        if name:
            source['name'] = name
        cls = _str_to_cls[source['doc_type']]
        app = cls.from_source(source, domain)
        app.save()
        app_id = app._id
        return back_to_main(**locals())
    else:
        app_id = req.GET.get('app')
        redirect_domain = req.GET.get('domain')
        if redirect_domain:
            return HttpResponseRedirect(
                reverse('import_app', args=[redirect_domain])
                + "?app={app_id}".format(app_id=app_id)
            )
        
        if app_id:
            app = Application.get(app_id)
            assert(app.doc_type in ('Application', 'RemoteApp'))
            assert(req.couch_user.is_member_of(app.domain))
        else: 
            app = None
        
        return render_to_response(req, template, {'domain': domain, 'app': app})

@require_permission('edit-apps')
@require_POST
def import_factory_app(req, domain):
    factory_app = get_app('factory', req.POST['app_id'])
    source = factory_app.export_json(dump_json=False)
    name = req.POST.get('name')
    if name:
        source['name'] = name
    cls = _str_to_cls[source['doc_type']]
    app = cls.from_source(source, domain)
    app.save()
    app_id = app._id
    return back_to_main(**locals())

@require_permission('edit-apps')
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

@require_permission('edit-apps')
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
    return view_app(req, domain, app_id='')

def get_form_view_context(request, form, langs, is_user_registration):
    try:
        xform_questions = form.get_questions(langs) if form.contents and not is_user_registration else []
        # this is just to validate that the case and meta blocks can be created
        xform_errors = None
    except XMLSyntaxError as e:
        xform_questions = []
        messages.error(request, "%s" % e)
    except AppError, e:
        xform_questions = []
        messages.error(request, "Error in application: %s" % e)
    except XFormValidationError, e:
        xform_questions = []
        message = unicode(e)
        # Don't display the first two lines which say "Parsing form..." and 'Title: "{form_name}"'
        for msg in message.split("\n")[2:]:
            messages.error(request, "%s" % msg)
    except XFormError, e:
        xform_questions = []
        messages.error(request, "Error in form: %s" % e)
    # any other kind of error should fail hard, but for now there are too many for that to be practical
    except Exception, e:
        if settings.DEBUG:
            raise
        logging.exception(e)
        xform_questions = []
        messages.error(request, "Unexpected System Error: %s" % e)

    try:
        if form.contents:
            form.render_xform()
    except CaseError, e:
        messages.error(request, "Error in Case Management: %s" % e)
    except XFormValidationError, e:
        messages.error(request, "%s" % e)
    except Exception, e:
        if settings.DEBUG:
            raise
        logging.exception(e)
        messages.error(request, "Unexpected Error: %s" % e)

    try:
        languages = form.wrapped_xform().get_languages()
    except Exception:
        languages = []

    return {
        'nav_form': form if not is_user_registration else '',
        'xform_languages': languages,
        "xform_questions": xform_questions,
        'form_actions': form.actions.to_json(),
        'case_reserved_words_json': load_case_reserved_words(),
        'is_user_registration': is_user_registration,
    }

def get_apps_base_context(request, domain, app):

    applications = []
    for _app in ApplicationBase.view('app_manager/applications_brief', startkey=[domain], endkey=[domain, {}]):
        applications.append(_app)


    lang = request.GET.get('lang',
       request.COOKIES.get('lang', app.langs[0] if hasattr(app, 'langs') and app.langs else '')
    )

    if app and hasattr(app, 'langs'):
        if not app.langs:
            # lots of things fail if the app doesn't have any languages.
            # the best we can do is add 'en' if there's nothing else.
            app.langs.append('en')
            app.save()
        if not lang or lang not in app.langs:
            lang = app.langs[0]
        langs = [lang] + app.langs

    if app:
        saved_apps = ApplicationBase.view('app_manager/saved_app',
            startkey=[domain, app.id, {}],
            endkey=[domain, app.id],
            descending=True
        ).all()
    else:
        saved_apps = []
    context = locals()
    context.update(get_sms_autocomplete_context(request, domain))
    return context

def view_generic(req, domain, app_id='', module_id=None, form_id=None, is_user_registration=False):
    """
    This is the main view for the app. All other views redirect to here.

    """
    def bail():
        module_id=''
        form_id=''
        messages.error(req, 'Oops! We could not complete your request. Please try again')
        return back_to_main(req, domain, app_id)

    edit = (req.GET.get('edit', '') == 'true') and req.couch_user.can_edit_apps(domain)

    if form_id and not module_id:
        return bail()

    app = module = form = None
    try:
        if app_id:
            app = get_app(domain, app_id)
        if is_user_registration:
            form = app.get_user_registration()
        if module_id:
            module = app.get_module(module_id)
        if form_id:
            form = module.get_form(form_id)
    except IndexError:
        return bail()

    base_context = get_apps_base_context(req, domain, app)
    applications = base_context['applications']
    if not app and applications:
        app_id = applications[0]['id']
        del edit
        return back_to_main(edit=False, **locals())
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
        for _form in module.forms:
            case_properties.update(_form.actions.update_case.update.keys())
    case_properties = sorted(case_properties)


    build_errors_id = req.GET.get('build_errors', "")
    build_errors = []
    if build_errors_id:
        try:
            error_doc = BuildErrors.get(build_errors_id)
            build_errors = error_doc.errors
            error_doc.delete()
        except ResourceNotFound:
            pass
    context = {
        'domain': domain,
        'applications': applications,

        'app': app,
        'module': module,
        'form': form,

        'case_properties': case_properties,

        'new_module_form': NewModuleForm(),
        'new_xform_form': NewXFormForm(),
        'edit': edit,

#        'factory_apps': factory_apps,
        'editor_url': settings.EDITOR_URL,
        'URL_BASE': get_url_base(),
        'XFORMPLAYER_URL': reverse('xform_play_remote'),

        'build_errors': build_errors,
    }
    context.update(base_context)
    if app and not module and hasattr(app, 'translations'):
        context.update({"translations": app.translations.get(context['lang'], {})})

    if form:
        template="app_manager/form_view.html"
        context.update(get_form_view_context(req, form, context['langs'], is_user_registration))
    elif module:
        template="app_manager/module_view.html"
    else:
        template="app_manager/app_view.html"
    error = req.GET.get('error', '')

    force_edit = False
    if (not context['applications']) or (app and app.doc_type == "Application" and not app.modules):
        edit = True
        force_edit = True
    context.update({
        'force_edit': force_edit,
        'error':error,
        'app': app,
    })
    if app:
        options = CommCareBuildConfig.fetch().menu
        is_standard_build = [o.build.to_string() for o in options if o.build.to_string() == app.build_spec.to_string()]
        context.update({
            "commcare_build_options": options,
            "is_standard_build": bool(is_standard_build)
        })

    response = render_to_response(req, template, context)
    response.set_cookie('lang', _encode_if_unicode(context['lang']))
    return response

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
def view_app(req, domain, app_id=''):
    # redirect old m=&f= urls
    module_id = req.GET.get('m', None)
    form_id = req.GET.get('f', None)
    if module_id or form_id:
        return back_to_main(**locals())
    return view_generic(req, domain, app_id)

@login_and_domain_required
def form_contents(req, domain, app_id, module_id, form_id):
    return form_designer(req, domain, app_id, module_id, form_id)

@login_and_domain_required
def user_registration_contents(req, domain, app_id):
    return form_designer(req, domain, app_id, is_user_registration=True)

@login_and_domain_required
def form_designer(req, domain, app_id, module_id=None, form_id=None, is_user_registration=False):
    app = get_app(domain, app_id)

    if is_user_registration:
        form = app.user_registration
    else:
        module = app.get_module(module_id)
        form = module.get_form(form_id)

    edit = True

    context = get_apps_base_context(req, domain, app)
    context.update(locals())
    return render_to_response(req, 'app_manager/form_designer.html', context)



@require_POST
@require_permission('edit-apps')
def new_app(req, domain):
    "Adds an app to the database"
    lang = req.COOKIES.get('lang', "en")
    type = req.POST["type"]
    cls = _str_to_cls[type]
    app = cls.new_app(domain, "Untitled Application", lang)
    if cls == Application:
        app.new_module("Untitled Module", lang)
        app.new_form(0, "Untitled Form", lang)
        module_id = 0
        form_id = 0
    app.save()
    app_id = app.id

    return back_to_main(**locals())

@require_POST
@require_permission('edit-apps')
def new_module(req, domain, app_id):
    "Adds a module to an app"
    app = get_app(domain, app_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    name = req.POST.get('name')
    module = app.new_module(name, lang)
    module_id = module.id
    app.new_form(module_id, "Untitled Form", lang)
    app.save()
    return back_to_main(**locals())

@require_POST
@require_permission('edit-apps')
def new_form(req, domain, app_id, module_id):
    "Adds a form to an app (under a module)"
    app = get_app(domain, app_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    name = req.POST.get('name')
    form = app.new_form(module_id, name, lang)
    app.save()
    # add form_id to locals()
    form_id = form.id
    return back_to_main(**locals())

@require_POST
@require_permission('edit-apps')
def delete_app(req, domain, app_id):
    "Deletes an app from the database"
    get_app(domain, app_id).delete()
    del app_id
    return back_to_main(**locals())

@require_POST
@require_permission('edit-apps')
def delete_module(req, domain, app_id, module_id):
    "Deletes a module from an app"
    app = get_app(domain, app_id)
    app.delete_module(module_id)
    app.save()
    del module_id
    return back_to_main(**locals())

@require_POST
@require_permission('edit-apps')
def delete_form(req, domain, app_id, module_id, form_id):
    "Deletes a form from an app"
    app = get_app(domain, app_id)
    app.delete_form(module_id, form_id)
    app.save()
    del form_id
    return back_to_main(**locals())

@require_POST
@require_permission('edit-apps')
def edit_module_attr(req, domain, app_id, module_id, attr):
    """
    Called to edit any (supported) module attribute, given by attr
    """
    attributes = {
        "all": None,
        "case_type": None, "put_in_root": None,
        "name": None, "case_label": None, "referral_label": None,
        "case_list": ('case_list-show', 'case_list-label'),
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
                return req.POST.get(attribute)

    app = get_app(domain, app_id)
    module = app.get_module(module_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    resp = {'update': {}}
    if should_edit("case_type"):
        module["case_type"] = req.POST.get("case_type", None)
    if should_edit("put_in_root"):
        module["put_in_root"] = json.loads(req.POST.get("put_in_root"))
    for attribute in ("name", "case_label", "referral_label"):
        if should_edit(attribute):
            name = req.POST.get(attribute, None)
            module[attribute][lang] = name
            if should_edit("name"):
                resp['update'].update({'.variable-module_name': module.name[lang]})
    if should_edit("case_list"):
        module["case_list"].show = json.loads(req.POST['case_list-show'])
        module["case_list"].label[lang] = req.POST['case_list-label']
    app.save(resp)
    return HttpResponse(json.dumps(resp))

@require_POST
@require_permission('edit-apps')
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
@require_permission('edit-apps')
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
@require_permission('edit-apps')
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

@require_POST
@require_permission('edit-apps')
def edit_form_attr(req, domain, app_id, unique_form_id, attr):
    """
    Called to edit any (supported) form attribute, given by attr

    """
    app = get_app(domain, app_id)
    form = app.get_form(unique_form_id)
    lang = req.COOKIES.get('lang', app.langs[0])
    ajax = json.loads(req.POST.get('ajax', 'true'))

    resp = {}

    if   "requires" == attr:
        requires = req.POST['requires']
        form.set_requires(requires)
    elif "name" == attr:
        name = req.POST['name']
        form.name[lang] = name
        resp['update'] = {'.variable-form_name': form.name[lang]}
    elif "xform" == attr:
        error = None
        try:
            xform = req.FILES.get('xform').read()
            try:
                xform = unicode(xform, encoding="utf-8")
            except Exception:
                error = "Error uploading form: Please make sure your form is encoded in UTF-8"
        except Exception:
            xform = req.POST.get('xform')

        if xform:
            form.contents = xform
            form.refresh()
        else:
            error = "You didn't select a form to upload"
        if error:
            if ajax:
                return HttpResponseBadRequest(error)
            else:
                messages.error(req, error)
    elif "show_count" == attr:
        show_count = req.POST['show_count']
        form.show_count = True if show_count == "True" else False
    elif "put_in_root" == attr:
        put_in_root = req.POST['put_in_root']
        form.put_in_root = True if put_in_root == "True" else False
    app.save(resp)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(**locals())

@require_POST
@require_permission('edit-apps')
def rename_language(req, domain, form_unique_id):
    old_code = req.POST.get('oldCode')
    new_code = req.POST.get('newCode')
    form, app = Form.get_form(form_unique_id, and_app=True)
    if app.domain != domain:
        raise Http404
    try:
        form.rename_xform_language(old_code, new_code)
        app.save()
        return HttpResponse(json.dumps({"status": "ok"}))
    except XFormError as e:
        response = HttpResponse(json.dumps({'status': 'error', 'message': unicode(e)}))
        response.status_code = 409
        return response

@require_POST
@require_permission('edit-apps')
def edit_form_actions(req, domain, app_id, module_id, form_id):
    app = get_app(domain, app_id)
    form = app.get_module(module_id).get_form(form_id)
    form.actions = FormActions.wrap(json.loads(req.POST['actions']))
    response_json = {}
    app.save(response_json)
    return json_response(response_json)

@require_permission('edit-apps')
def multimedia_list_download(req, domain, app_id):
    app = get_app(domain, app_id)
    include_audio = req.GET.get("audio", True)
    include_images = req.GET.get("images", True)
    strip_jr = req.GET.get("strip_jr", True)
    filelist = []
    for m in app.get_modules():
        for f in m.get_forms():
            parsed = XForm(f.contents)
            if include_images:
                filelist.extend(parsed.image_references)
            if include_audio:
                filelist.extend(parsed.audio_references)
    
    if strip_jr:
        filelist = [s.replace("jr://file/", "") for s in filelist if s]
    response = HttpResponse()
    response['Content-Disposition'] = 'attachment; filename=list.txt' 
    response.write("\n".join(sorted(set(filelist))))
    return response
        
@require_permission('edit-apps')
def multimedia_home(req, domain, app_id, module_id=None, form_id=None):
    """
    Edit multimedia for forms
    """
    app = get_app(domain, app_id)
    
    parsed_forms = {}
    images = {} 
    audio_files = {}
    # TODO: make this more fully featured
    for m in app.get_modules():
        for f in m.get_forms():
            parsed = XForm(f.contents)
            parsed_forms[f] = parsed
            for i in parsed.image_references:
                if i not in images: images[i] = []
                images[i].append((m,f)) 
            for i in parsed.audio_references:
                if i not in audio_files: audio_files[i] = []
                audio_files[i].append((m,f)) 
    
    sorted_images = SortedDict()
    sorted_audio = SortedDict()
    for k in sorted(images):
        sorted_images[k] = images[k]
    for k in sorted(audio_files):
        sorted_audio[k] = audio_files[k]
    return render_to_response(req, "app_manager/multimedia_home.html", 
                              {"domain": domain,
                               "app": app,
                               "images": sorted_images,
                               "audiofiles": sorted_audio})

@require_GET
@login_and_domain_required
def commcare_profile(req, domain, app_id):
    app = get_app(domain, app_id)
    return HttpResponse(json.dumps(app.profile))

@require_POST
@require_permission('edit-apps')
def edit_commcare_profile(req, domain, app_id):
    try:
        profile = json.loads(req.POST.get('profile'))
    except TypeError:
        return HttpResponseBadRequest(json.dumps({
            'reason': "Must have a param called profile set to: {\"properites\": {...}, \"features\": {...}}"
        }))
    app = get_app(domain, app_id)
    changed = defaultdict(dict)
    for type in ["features", "properties"]:
        for name, value in profile.get(type, {}).items():
            if type not in app.profile:
                app.profile[type] = {}
            app.profile[type][name] = value
            changed[type][name] = value
    response_json = {"status": "ok", "changed": changed}
    app.save(response_json)
    return json_response(response_json)

@require_POST
@require_permission('edit-apps')
def edit_app_lang(req, domain, app_id):
    """
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
            app.langs.append(lang)
            app.save()
    else:
        try:
            app.rename_lang(app.langs[lang_id], lang)
        except AppError as e:
            messages.error(req, unicode(e))
        else:
            app.save()

    return back_to_main(**locals())

@require_edit_apps
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
@require_permission('edit-apps')
def delete_app_lang(req, domain, app_id):
    """
    Called when a language (such as 'zh') is to be deleted from app.langs

    """
    lang_id = int(req.POST['index'])
    app = get_app(domain, app_id)
    del app.langs[lang_id]
    app.save()
    return back_to_main(**locals())

@require_POST
@require_permission('edit-apps')
def edit_app_attr(req, domain, app_id, attr):
    """
    Called to edit any (supported) app attribute, given by attr

    """
    app = get_app(domain, app_id)
    lang = req.COOKIES.get('lang', app.langs[0])

    attributes = [
        'all',
        'recipients', 'name', 'success_message', 'use_commcare_sense',
        'native_input', 'build_spec', 'show_user_registration'
        # RemoteApp only
        'profile_url'
    ]
    if attr not in attributes:
        return HttpResponseBadRequest()
    
    def should_edit(attribute):
        return attribute == attr or ('all' == attr and req.POST.get(attribute))
    resp = {"update": {}}
    # For either type of app
    if should_edit("recipients"):
        recipients = req.POST['recipients']
        app.recipients = recipients
    if should_edit("name"):
        name = req.POST["name"]
        app.name = name
        resp['update'].update({'.variable-app_name': name})
    if should_edit("success_message"):
        success_message = req.POST['success_message']
        app.success_message[lang] = success_message
    if should_edit("use_commcare_sense"):
        use_commcare_sense = json.loads(req.POST.get('use_commcare_sense', 'false'))
        app.use_commcare_sense = use_commcare_sense
    if should_edit("native_input"):
        native_input = json.loads(req.POST['native_input'])
        app.native_input = native_input
    if should_edit("build_spec"):
        build_spec = req.POST['build_spec']
        app.build_spec = BuildSpec.from_string(build_spec)
    if should_edit("show_user_registration"):
        app.show_user_registration = bool(json.loads(req.POST['show_user_registration']))
    # For RemoteApp
    if should_edit("profile_url"):
        if app.doc_type not in ("RemoteApp",):
            raise Exception("App type %s does not support profile url" % app.doc_type)
        app['profile_url'] = req.POST['profile_url']
    app.save(resp)
    return HttpResponse(json.dumps(resp))


@require_POST
@require_permission('edit-apps')
def rearrange(req, domain, app_id, key):
    """
    This function handels any request to switch two items in a list.
    Key tells us the list in question and must be one of
    'forms', 'modules', 'detail', or 'langs'. The two POST params
    'to' and 'from' give us the indicies of the items to be rearranged.

    """
    app = get_app(domain, app_id)
    ajax = json.loads(req.POST.get('ajax', 'false'))
    i, j = (int(x) for x in (req.POST['to'], req.POST['from']))
    resp = {}


    if   "forms" == key:
        module_id = int(req.POST['module_id'])
        app.rearrange_forms(module_id, i, j)
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

@require_POST
@require_permission('edit-apps')
def save_copy(req, domain, app_id):
    """
    Saves a copy of the app to a new doc.
    See VersionedDoc.save_copy

    """
    next = req.POST.get('next')
    comment = req.POST.get('comment')
    app = get_app(domain, app_id)
    errors = app.validate_app()
    def replace_params(next, **kwargs):
        """this is a more general function that should be moved"""
        url = urlparse.urlparse(next)
        q = urlparse.parse_qs(url.query)
        for param in kwargs:
            if isinstance(kwargs[param], basestring):
                q[param] = [kwargs[param]]
            else:
                q[param] = kwargs[param]
        url = url._replace(query=urllib.urlencode(q, doseq=True))
        next = urlparse.urlunparse(url)
        return next
    if not errors:
        app.save_copy(comment=comment)
    else:
        errors = BuildErrors(errors=errors)
        errors.save()
        next = replace_params(next, build_errors=errors.get_id)
    return HttpResponseRedirect(next)

@require_POST
@require_permission('edit-apps')
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
@require_permission('edit-apps')
def delete_copy(req, domain, app_id):
    """
    Deletes a saved copy permanently from the database.
    See VersionedDoc.delete_copy

    """
    next = req.POST.get('next')
    app = get_app(domain, app_id)
    copy = get_app(domain, req.POST['saved_app'])
    app.delete_copy(copy)
    return HttpResponseRedirect(next)

# download_* views are for downloading the files that the application generates
# (such as CommCare.jad, suite.xml, profile.xml, etc.

BAD_BUILD_MESSAGE = "Sorry: this build is invalid. Try deleting it and rebuilding. If error persists, please contact us at commcarehq-support@dimagi.com"

@safe_download
def download_index(req, domain, app_id, template="app_manager/download_index.html"):
    """
    A landing page, mostly for debugging, that has links the jad and jar as well as
    all the resource files that will end up zipped into the jar.

    """
    app = get_app(domain, app_id)
    return render_to_response(req, template, {
        'app': app,
        'files': sorted(app.create_all_files().items()),
    })

@safe_download
def download_profile(req, domain, app_id):
    """
    See ApplicationBase.create_profile

    """
    return HttpResponse(
        get_app(domain, app_id).create_profile()
    )

def odk_install(req, domain, app_id):
    return render_to_response(req, "app_manager/odk_install.html",
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
        get_app(domain, app_id).create_profile(is_odk=True),
        mimetype="commcare/profile"
    )

@safe_download
def download_suite(req, domain, app_id):
    """
    See Application.create_suite

    """
    return HttpResponse(
        get_app(domain, app_id).create_suite()
    )

@safe_download
def download_app_strings(req, domain, app_id, lang):
    """
    See Application.create_app_strings

    """
    return HttpResponse(
        get_app(domain, app_id).create_app_strings(lang)
    )

@safe_download
def download_xform(req, domain, app_id, module_id, form_id):
    """
    See Application.fetch_xform

    """
    return HttpResponse(
        get_app(domain, app_id).fetch_xform(module_id, form_id)
    )

@safe_download
def download_user_registration(req, domain, app_id):
    """See Application.fetch_xform"""
    return HttpResponse(
        get_app(domain, app_id).get_user_registration().render_xform()
    )

@safe_download
def download_jad(req, domain, app_id):
    """
    See ApplicationBase.create_jadjar

    """
    app = get_app(domain, app_id)
    try:
        jad, _ = app.create_jadjar()
    except ResourceConflict:
        return download_jad(req, domain, app_id)
    try:
        response = HttpResponse(jad)
    except Exception:
        messages.error(req, BAD_BUILD_MESSAGE)
        return back_to_main(**locals())
    response["Content-Disposition"] = "filename=%s.jad" % "CommCare"
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
    app = get_app(domain, app_id)
    _, jar = app.create_jadjar()
    response['Content-Disposition'] = "filename=%s.jar" % "CommCare"
    response['Content-Length'] = len(jar)
    try:
        response.write(jar)
    except Exception:
        messages.error(req, BAD_BUILD_MESSAGE)
        return back_to_main(**locals())
    return response

@safe_download
def download_raw_jar(req, domain, app_id):
    """
    See ApplicationBase.fetch_jar

    """
    response = HttpResponse(
        get_app(domain, app_id).fetch_jar()
    )
    response['Content-Type'] = "application/java-archive"
    return response

def emulator(req, domain, app_id, template="app_manager/emulator.html"):
    app = get_app(domain, app_id)
    if app.copy_of:
        app = get_app(domain, app.copy_of)
    return render_to_response(req, template, {
        'domain': domain,
        'app': app,
        'build_path': "/builds/1.2.dev/7106/Generic/WebDemo/",
    })

def emulator_commcare_jar(req, domain, app_id):
    response = HttpResponse(
        get_app(domain, app_id).fetch_emulator_commcare_jar()
    )
    response['Content-Type'] = "application/java-archive"
    return response
