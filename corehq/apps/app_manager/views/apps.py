import copy
import json
from collections import defaultdict
from StringIO import StringIO

from django.core.cache import cache
from django.utils.translation import ugettext as _, get_language
from django.utils.http import urlencode as django_urlencode
from couchdbkit.exceptions import ResourceConflict
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.contrib import messages

from corehq.apps.app_manager.commcare_settings import get_commcare_settings_layout
from corehq.apps.app_manager.exceptions import ConflictingCaseTypeError, \
    IncompatibleFormTypeException, RearrangeError
from corehq.apps.app_manager.views.utils import back_to_main, get_langs, \
    validate_langs, CASE_TYPE_CONFLICT_MSG
from corehq import toggles, privileges
from corehq.apps.app_manager.forms import CopyApplicationForm
from corehq.apps.app_manager import id_strings
from corehq.apps.hqwebapp.models import ApplicationsTab
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.translations.models import Translation
from corehq.apps.app_manager.const import (
    APP_V1,
    APP_V2,
    MAJOR_RELEASE_TO_VERSION,
)
from corehq.apps.app_manager.success_message import SuccessMessage
from corehq.apps.app_manager.util import (
    get_settings_values,
)
from corehq.apps.domain.models import Domain
from corehq.util.compression import decompress
from corehq.apps.app_manager.xform import (
    XFormException, XForm)
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.util.view_utils import set_file_download
from couchexport.export import FormattedRow
from couchexport.models import Format
from couchexport.writers import Excel2007ExportWriter
from dimagi.utils.django.cache import make_template_fragment_key
from dimagi.utils.web import json_response, json_request
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_or_digest,
)
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    Application,
    ApplicationBase,
    DeleteApplicationRecord,
    Form,
    FormNotFoundException,
    Module,
    ModuleNotFoundException,
    load_app_template,
    str_to_cls,
)
from corehq.apps.app_manager.models import import_app as import_app_util
from dimagi.utils.web import get_url_base
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps
from django_prbac.utils import has_privilege


@no_conflict_require_POST
@require_can_edit_apps
def delete_app(request, domain, app_id):
    "Deletes an app from the database"
    app = get_app(domain, app_id)
    record = app.delete_app()
    messages.success(request,
        'You have deleted an application. <a href="%s" class="post-link">Undo</a>' % reverse(
            'undo_delete_app', args=[domain, record.get_id]
        ),
        extra_tags='html'
    )
    app.save()
    clear_app_cache(request, domain)
    return back_to_main(request, domain)


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
    clear_app_cache(request, domain)
    messages.success(request, 'Application successfully restored.')
    return back_to_main(request, domain, app_id=app_id)


@require_can_edit_apps
def default_new_app(request, domain):
    """New Blank Application according to defaults. So that we can link here
    instead of creating a form and posting to the above link, which was getting
    annoying for the Dashboard.
    """
    lang = 'en'
    app = Application.new_app(
        domain, _("Untitled Application"), lang=lang,
        application_version=APP_V2
    )
    module = Module.new_module(_("Untitled Module"), lang)
    app.add_module(module)
    form = app.new_form(0, "Untitled Form", lang)
    if request.project.secure_submissions:
        app.secure_submissions = True
    clear_app_cache(request, domain)
    app.save()
    return back_to_main(request, domain, app_id=app.id, module_id=module.id, form_id=form.id)


def get_app_view_context(request, app):

    is_cloudcare_allowed = has_privilege(request, privileges.CLOUDCARE)
    context = {}

    settings_layout = copy.deepcopy(
        get_commcare_settings_layout()[app.get_doc_type()])
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

    if toggles.CUSTOM_PROPERTIES.enabled(request.domain) and 'custom_properties' in app.profile:
        custom_properties_array = map(lambda p: {'key': p[0], 'value': p[1]},
                                      app.profile.get('custom_properties').items())
        context.update({'custom_properties': custom_properties_array})

    context.update({
        'settings_layout': settings_layout,
        'settings_values': get_settings_values(app),
        'is_cloudcare_allowed': is_cloudcare_allowed,
    })

    build_config = CommCareBuildConfig.fetch()
    options = build_config.get_menu()
    if not request.user.is_superuser:
        options = [option for option in options if not option.superuser_only]
    options_map = defaultdict(lambda: {"values": [], "value_names": []})
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


def clear_app_cache(request, domain):
    ApplicationBase.get_db().view('app_manager/applications_brief',
        startkey=[domain],
        limit=1,
    ).all()
    for is_active in True, False:
        key = make_template_fragment_key('header_tab', [
            domain,
            None,  # tab.org should be None for any non org page
            ApplicationsTab.view,
            is_active,
            request.couch_user.get_id,
            get_language(),
        ])
        cache.delete(key)


def get_apps_base_context(request, domain, app):

    lang, langs = get_langs(request, app)

    if getattr(request, 'couch_user', None):
        timezone = get_timezone_for_user(request.couch_user, domain)
    else:
        timezone = None

    context = {
        'lang': lang,
        'langs': langs,
        'domain': domain,
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
            'show_care_plan': (
                v2_app
                and not app.has_careplan_module
                and toggles.APP_BUILDER_CAREPLAN.enabled(request.user.username)
            ),
            'show_advanced': (
                v2_app
                and (
                    toggles.APP_BUILDER_ADVANCED.enabled(request.user.username)
                    or getattr(app, 'commtrack_enabled', False)
                )
            ),
        })

    return context


@login_or_digest
@require_can_edit_apps
def app_source(request, domain, app_id):
    app = get_app(domain, app_id)
    return HttpResponse(app.export_json())


@require_can_edit_apps
def copy_app_check_domain(request, domain, name, app_id):
    app_copy = import_app_util(app_id, domain, {'name': name})
    return back_to_main(request, app_copy.domain, app_id=app_copy._id)


@require_can_edit_apps
def copy_app(request, domain):
    app_id = request.POST.get('app')
    form = CopyApplicationForm(app_id, request.POST)
    if form.is_valid():
        return copy_app_check_domain(request, form.cleaned_data['domain'], form.cleaned_data['name'], app_id)
    else:
        from corehq.apps.app_manager.views.view_generic import view_generic
        return view_generic(request, domain, app_id=app_id, copy_app_form=form)


@require_can_edit_apps
def app_from_template(request, domain, slug):
    clear_app_cache(request, domain)
    template = load_app_template(slug)
    app = import_app_util(template, domain, {
        'created_from_template': '%s' % slug,
    })
    module_id = 0
    form_id = 0
    try:
        app.get_module(module_id).get_form(form_id)
    except (ModuleNotFoundException, FormNotFoundException):
        return HttpResponseRedirect(reverse('view_app', args=[domain, app._id]))
    return HttpResponseRedirect(reverse('view_form', args=[domain, app._id, module_id, form_id]))


@require_can_edit_apps
def import_app(request, domain, template="app_manager/import_app.html"):
    if request.method == "POST":
        clear_app_cache(request, domain)
        name = request.POST.get('name')
        compressed = request.POST.get('compressed')

        valid_request = True
        if not name:
            messages.error(request, _("You must submit a name for the application you are importing."))
            valid_request = False
        if not compressed:
            messages.error(request, _("You must submit the source data."))
            valid_request = False

        if not valid_request:
            return render(request, template, {'domain': domain})

        source = decompress([chr(int(x)) if int(x) < 256 else int(x) for x in compressed.split(',')])
        source = json.loads(source)
        assert(source is not None)
        app = import_app_util(source, domain, {'name': name})

        return back_to_main(request, domain, app_id=app._id)
    else:
        app_id = request.GET.get('app')
        redirect_domain = request.GET.get('domain') or None
        if redirect_domain is not None:
            redirect_domain = redirect_domain.lower()
            if Domain.get_by_name(redirect_domain):
                return HttpResponseRedirect(
                    reverse('import_app', args=[redirect_domain])
                    + "?app={app_id}".format(app_id=app_id)
                )
            else:
                if redirect_domain:
                    messages.error(request, "We can't find a project called %s." % redirect_domain)
                else:
                    messages.error(request, "You left the project name blank.")
                return HttpResponseRedirect(request.META.get('HTTP_REFERER', request.path))

        if app_id:
            app = get_app(None, app_id)
            assert(app.get_doc_type() in ('Application', 'RemoteApp'))
            assert(request.couch_user.is_member_of(app.domain))
        else:
            app = None

        return render(request, template, {
            'domain': domain,
            'app': app,
            'is_superuser': request.couch_user.is_superuser
        })


@require_GET
@require_deploy_apps
def view_app(request, domain, app_id=None):
    from corehq.apps.app_manager.views.view_generic import view_generic
    # redirect old m=&f= urls
    module_id = request.GET.get('m', None)
    form_id = request.GET.get('f', None)
    if module_id or form_id:
        return back_to_main(request, domain, app_id=app_id, module_id=module_id,
                            form_id=form_id)

    return view_generic(request, domain, app_id)


@no_conflict_require_POST
@require_can_edit_apps
def new_app(request, domain):
    "Adds an app to the database"
    lang = 'en'
    type = request.POST["type"]
    application_version = request.POST.get('application_version', APP_V1)
    cls = str_to_cls[type]
    form_args = []
    if cls == Application:
        app = cls.new_app(domain, "Untitled Application", lang=lang, application_version=application_version)
        module = Module.new_module("Untitled Module", lang)
        app.add_module(module)
        form = app.new_form(0, "Untitled Form", lang)
        form_args = [module.id, form.id]
    else:
        app = cls.new_app(domain, "Untitled Application", lang=lang)
    if request.project.secure_submissions:
        app.secure_submissions = True
    app.save()
    clear_app_cache(request, domain)
    main_args = [request, domain, app.id]
    main_args.extend(form_args)

    return back_to_main(*main_args)


@no_conflict_require_POST
@require_can_edit_apps
def rename_language(request, domain, form_unique_id):
    old_code = request.POST.get('oldCode')
    new_code = request.POST.get('newCode')
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
        response = HttpResponse(json.dumps({'status': 'error', 'message': unicode(e)}), status=409)
        return response


@require_GET
@login_and_domain_required
def validate_language(request, domain, app_id):
    app = get_app(domain, app_id)
    term = request.GET.get('term', '').lower()
    if term in [lang.lower() for lang in app.langs]:
        return HttpResponse(json.dumps({'match': {"code": term, "name": term}, 'suggestions': []}))
    else:
        return HttpResponseRedirect(
            "%s?%s" % (
                reverse('langcodes.views.validate', args=[]),
                django_urlencode({'term': term})
            )
        )


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
def delete_app_lang(request, domain, app_id):
    """
    DEPRECATED
    Called when a language (such as 'zh') is to be deleted from app.langs

    """
    lang_id = int(request.POST['index'])
    app = get_app(domain, app_id)
    del app.langs[lang_id]
    app.save()
    return back_to_main(request, domain, app_id=app_id)


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
        clear_app_cache(request, domain)
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
        if not has_privilege(request, privileges.CLOUDCARE):
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


@require_can_edit_apps
def get_commcare_version(request, app_id, app_version):
    options = CommCareBuildConfig.fetch().get_menu(app_version)
    return json_response(options)


@no_conflict_require_POST
@require_can_edit_apps
def rearrange(request, domain, app_id, key):
    """
    This function handles any request to switch two items in a list.
    Key tells us the list in question and must be one of
    'forms', 'modules', 'detail', or 'langs'. The two POST params
    'to' and 'from' give us the indicies of the items to be rearranged.

    """
    app = get_app(domain, app_id)
    ajax = json.loads(request.POST.get('ajax', 'false'))
    i, j = (int(x) for x in (request.POST['to'], request.POST['from']))
    resp = {}
    module_id = None

    try:
        if "forms" == key:
            to_module_id = int(request.POST['to_module_id'])
            from_module_id = int(request.POST['from_module_id'])
            try:
                app.rearrange_forms(to_module_id, from_module_id, i, j)
            except ConflictingCaseTypeError:
                messages.warning(request, CASE_TYPE_CONFLICT_MSG, extra_tags="html")
        elif "modules" == key:
            app.rearrange_modules(i, j)
    except IncompatibleFormTypeException:
        messages.error(request, _(
            'The form can not be moved into the desired module.'
        ))
        return back_to_main(request, domain, app_id=app_id, module_id=module_id)
    except (RearrangeError, ModuleNotFoundException):
        messages.error(request, _(
            'Oops. '
            'Looks like you got out of sync with us. '
            'The sidebar has been updated, so please try again.'
        ))
        return back_to_main(request, domain, app_id=app_id, module_id=module_id)
    app.save(resp)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(request, domain, app_id=app_id, module_id=module_id)


@require_can_edit_apps
def formdefs(request, domain, app_id):
    # TODO: Looks like this function is never used
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
        response = HttpResponse(f.getvalue(), content_type=Format.from_format('xlsx').mimetype)
        set_file_download(response, 'formdefs.xlsx')
        return response
    else:
        return json_response(formdefs)
