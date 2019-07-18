from __future__ import absolute_import

from __future__ import unicode_literals
import copy
import json
import os
import tempfile
import urllib3
import zipfile
from collections import defaultdict
from wsgiref.util import FileWrapper

from couchdbkit.exceptions import ResourceConflict
from django.contrib import messages
from django.http import HttpResponse, Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import urlencode as django_urlencode
from django.utils.text import slugify
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET
from django_prbac.utils import has_privilege

from corehq import toggles, privileges
from corehq.apps.analytics.tasks import (
    HUBSPOT_APP_TEMPLATE_FORM_ID,
    send_hubspot_form,
    track_workflow,
)
from corehq.apps.app_manager import id_strings, add_ons
from corehq.apps.app_manager.commcare_settings import get_commcare_settings_layout
from corehq.apps.app_manager.const import (
    MAJOR_RELEASE_TO_VERSION,
    AUTO_SELECT_USERCASE,
)
from corehq.apps.app_manager.dbaccessors import get_app, get_current_app, get_latest_released_app_version
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps
from corehq.apps.app_manager.exceptions import IncompatibleFormTypeException, RearrangeError, AppLinkError
from corehq.apps.app_manager.forms import CopyApplicationForm
from corehq.apps.app_manager.models import (
    Application,
    ApplicationBase,
    DeleteApplicationRecord,
    Form,
    LinkedApplication,
    Module,
    ModuleNotFoundException,
    app_template_dir,
    load_app_template,
)
from corehq.apps.app_manager.models import import_app as import_app_util
from corehq.apps.app_manager.tasks import (
    make_async_build_v2,
    update_linked_app_and_notify_task
)
from corehq.apps.app_manager.util import (
    get_settings_values,
    app_doc_types,
    get_and_assert_practice_user_in_domain,
    get_latest_enabled_versions_per_profile,
)
from corehq.apps.app_manager.views.utils import back_to_main, get_langs, \
    validate_langs, update_linked_app, clear_xmlns_app_id_cache
from corehq.apps.app_manager.xform import (
    XFormException)
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.apps.cloudcare.views import FormplayerMain
from corehq.apps.dashboard.views import DomainDashboardView
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_or_digest,
    track_domain_request
)
from corehq.apps.domain.models import Domain
from corehq.apps.hqmedia.models import MULTIMEDIA_PREFIX, CommCareMultimedia
from corehq.apps.hqwebapp.forms import AppTranslationsBulkUploadForm
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.linked_domain.applications import create_linked_app
from corehq.apps.linked_domain.dbaccessors import is_master_linked_domain
from corehq.apps.linked_domain.exceptions import RemoteRequestError
from corehq.apps.translations.models import Translation
from corehq.apps.users.dbaccessors.all_commcare_users import get_practice_mode_mobile_workers
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.elastic import ESError
from corehq.tabs.tabclasses import ApplicationsTab
from corehq.util.compression import decompress
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.view_utils import reverse as reverse_util
from corehq.util.view_utils import set_file_download
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response, json_request
from toggle.shortcuts import set_toggle
import six
from io import open


@no_conflict_require_POST
@require_can_edit_apps
def delete_app(request, domain, app_id):
    "Deletes an app from the database"
    app = get_app(domain, app_id)
    record = app.delete_app()
    messages.success(
        request,
        _('You have deleted an application. <a href="%s" class="post-link">Undo</a>')
        % reverse('undo_delete_app', args=[domain, record.get_id]),
        extra_tags='html'
    )
    app.save()
    clear_app_cache(request, domain)
    clear_xmlns_app_id_cache(domain)
    return HttpResponseRedirect(reverse(DomainDashboardView.urlname, args=[domain]))


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
    send_hubspot_form(HUBSPOT_APP_TEMPLATE_FORM_ID, request)
    track_workflow(request.couch_user.username, "User created a new blank application")

    lang = 'en'
    app = Application.new_app(domain, _("Untitled Application"), lang=lang)
    add_ons.init_app(request, app)

    if request.project.secure_submissions:
        app.secure_submissions = True
    clear_app_cache(request, domain)
    app.save()
    return HttpResponseRedirect(reverse('view_app', args=[domain, app._id]))


def get_app_view_context(request, app):
    """
    This provides the context to render commcare settings on Edit Application Settings page

    This is where additional app or domain specific context can be added to any individual
    commcare-setting defined in commcare-app-settings.yaml or commcare-profile-settings.yaml
    """
    context = {}

    settings_layout = copy.deepcopy(
        get_commcare_settings_layout(app)
    )

    for section in settings_layout:
        new_settings = []
        for setting in section['settings']:
            toggle_name = setting.get('toggle')
            if toggle_name and not toggle_enabled(request, toggle_name):
                continue
            privilege_name = setting.get('privilege')
            if privilege_name and not has_privilege(request, privilege_name):
                continue
            disable_if_true = setting.get('disable_if_true')
            if disable_if_true and getattr(app, setting['id']):
                continue
            if app.get_doc_type() == 'LinkedApplication':
                if setting['id'] in app.SUPPORTED_SETTINGS:
                    if setting['id'] not in app.linked_app_attrs:
                        setting['is_inherited'] = True
            new_settings.append(setting)
        section['settings'] = new_settings

    app_view_options = {
        'permissions': {
            'cloudcare': has_privilege(request, privileges.CLOUDCARE),
        },
        'sections': settings_layout,
        'urls': {
            'save': reverse("edit_commcare_settings", args=(app.domain, app.id)),
        },
        'user': {
            'is_previewer': request.couch_user.is_previewer(),
        },
        'values': get_settings_values(app),
        'warning': _("This is not an allowed value for this field"),
    }
    if (app.get_doc_type() == 'Application'
            and toggles.CUSTOM_PROPERTIES.enabled(request.domain)
            and 'custom_properties' in getattr(app, 'profile', {})):
        custom_properties_array = [{'key': p[0], 'value': p[1]} for p in app.profile.get('custom_properties').items()]
        app_view_options.update({'customProperties': custom_properties_array})
    context.update({
        'app_view_options': app_view_options,
    })

    build_config = CommCareBuildConfig.fetch()
    options = build_config.get_menu()
    if not request.user.is_superuser and not toggles.IS_CONTRACTOR.enabled(request.user.username):
        options = [option for option in options if not option.superuser_only]
    options_map = defaultdict(lambda: {"values": [], "value_names": []})
    for option in options:
        builds = options_map[option.build.major_release()]
        builds["values"].append(option.build.to_string())
        builds["value_names"].append(option.get_label())
        if "default" not in builds:
            app_ver = MAJOR_RELEASE_TO_VERSION[option.build.major_release()]
            builds["default"] = build_config.get_default(app_ver).to_string()

    def _get_setting(setting_type, setting_id):
        # get setting dict from settings_layout
        if not settings_layout:
            return None
        matched = [x for x in [
                setting for section in settings_layout
                for setting in section['settings']
            ] if x['type'] == setting_type and x['id'] == setting_id]
        if matched:
            return matched[0]
        else:
            return None

    build_spec_setting = _get_setting('hq', 'build_spec')
    if build_spec_setting:
        build_spec_setting['options_map'] = options_map
        build_spec_setting['default_app_version'] = app.application_version

    practice_user_setting = _get_setting('hq', 'practice_mobile_worker_id')
    if practice_user_setting and has_privilege(request, privileges.PRACTICE_MOBILE_WORKERS):
        try:
            practice_users = get_practice_mode_mobile_workers(request.domain)
        except ESError:
            notify_exception(request, 'Error getting practice mode mobile workers')
            practice_users = []
        practice_user_setting['values'] = [''] + [u['_id'] for u in practice_users]
        practice_user_setting['value_names'] = [_('Not set')] + [u['username'] for u in practice_users]

    context.update({
        'bulk_ui_translation_upload': {
            'action': reverse('upload_bulk_ui_translations',
                              args=(app.domain, app.get_id)),
            'download_url': reverse('download_bulk_ui_translations',
                                    args=(app.domain, app.get_id)),
            'adjective': _("U\u200BI translation"),
            'plural_noun': _("U\u200BI translations"),
        },
        'bulk_app_translation_upload': {
            'action': reverse('upload_bulk_app_translations',
                              args=(app.domain, app.get_id)),
            'download_url': reverse('download_bulk_app_translations',
                                    args=(app.domain, app.get_id)),
            'adjective': _("app translation"),
            'plural_noun': _("app translations"),
            'can_select_language': toggles.BULK_UPDATE_MULTIMEDIA_PATHS.enabled_for_request(request),
            'can_validate_app_translations': toggles.VALIDATE_APP_TRANSLATIONS.enabled_for_request(request),
        },
    })
    context.update({
        'bulk_ui_translation_form': get_bulk_upload_form(
            context,
            context_key="bulk_ui_translation_upload",
        ),
        'bulk_app_translation_form': get_bulk_upload_form(
            context,
            context_key="bulk_app_translation_upload",
            form_class=AppTranslationsBulkUploadForm,
        ),
    })
    context.update({
        'smart_lang_display_enabled': getattr(app, 'smart_lang_display', False)
    })
    # Not used in APP_MANAGER_V2
    context['is_app_view'] = True

    if app.get_doc_type() == 'LinkedApplication':
        context['upstream_url'] = _get_upstream_url(app, request.couch_user)
        try:
            context['master_version'] = app.get_master_version()
        except RemoteRequestError:
            pass
    return context


def _get_upstream_url(app, request_user):
    """Get the upstream url if the user has access"""
    if (
            app.domain_link and (
                request_user.is_superuser or (
                    not app.domain_link.is_remote
                    and request_user.is_member_of(app.domain_link.master_domain)
                )
            )
    ):
        url = reverse('view_app', args=[app.domain_link.master_domain, app.master])
        if app.domain_link.is_remote:
            url = '{}{}'.format(app.domain_link.remote_base_url, url)
        return url


def clear_app_cache(request, domain):
    ApplicationBase.get_db().view('app_manager/applications_brief',
        startkey=[domain],
        limit=1,
    ).all()
    ApplicationsTab.clear_dropdown_cache(domain, request.couch_user.get_id)


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
        'app_subset': {
            'commcare_minor_release': app.commcare_minor_release,
            'doc_type': app.get_doc_type(),
            'form_counts_by_module': [len(m.forms) for m in app.modules] if not app.is_remote_app() else [],
            'version': app.version,
        } if app else {},
        'timezone': timezone,
    }

    if app and not app.is_remote_app():
        app.assert_app_v2()
        show_advanced = (
            toggles.APP_BUILDER_ADVANCED.enabled(domain)
            or getattr(app, 'commtrack_enabled', False)
        )

        show_biometric = (
            toggles.BIOMETRIC_INTEGRATION.enabled(domain)
            and app.is_biometric_enabled
        )

        disable_report_modules = (
            is_master_linked_domain(domain)
            and not toggles.MOBILE_UCR_LINKED_DOMAIN.enabled(domain)
        )

        # ideally this should be loaded on demand
        practice_users = []
        if app.enable_practice_users:
            try:
                practice_users = get_practice_mode_mobile_workers(request.domain)
            except ESError:
                notify_exception(request, 'Error getting practice mode mobile workers')

        latest_version_for_build_profiles = {}
        if toggles.RELEASE_BUILDS_PER_PROFILE.enabled(domain):
            latest_version_for_build_profiles = get_latest_enabled_versions_per_profile(app.get_id)

        context.update({
            'show_advanced': show_advanced,
            'show_biometric': show_biometric,
            'show_report_modules': toggles.MOBILE_UCR.enabled(domain),
            'disable_report_modules': disable_report_modules,
            'show_shadow_modules': toggles.APP_BUILDER_SHADOW_MODULES.enabled(domain),
            'show_shadow_forms': show_advanced,
            'show_training_modules': toggles.TRAINING_MODULE.enabled(domain) and app.enable_training_modules,
            'practice_users': [{"id": u['_id'], "text": u["username"]} for u in practice_users],
            'latest_version_for_build_profiles': latest_version_for_build_profiles,
        })

    return context


@login_or_digest
@require_can_edit_apps
def app_source(request, domain, app_id):
    app = get_app(domain, app_id)
    return json_response(app.export_json(dump_json=False))


@require_can_edit_apps
def copy_app(request, domain):
    app_id = request.POST.get('app')
    app = get_app(domain, app_id)
    form = CopyApplicationForm(
        domain, app, request.POST,
        export_zipped_apps_enabled=toggles.EXPORT_ZIPPED_APPS.enabled(request.user.username)
    )
    if not form.is_valid():
        from corehq.apps.app_manager.views.view_generic import view_generic
        return view_generic(request, domain, app_id=app_id, copy_app_form=form)

    gzip = request.FILES.get('gzip')
    if gzip:
        with zipfile.ZipFile(gzip, 'r', zipfile.ZIP_DEFLATED) as z:
            source = z.read(z.filelist[0].filename)
        app_id_or_source = source
    else:
        app_id_or_source = app_id

    def _inner(request, link_domain, data, master_domain=domain):
        clear_app_cache(request, link_domain)
        if data['toggles']:
            for slug in data['toggles'].split(","):
                set_toggle(slug, link_domain, True, namespace=toggles.NAMESPACE_DOMAIN)
        linked = data.get('linked')
        if linked:
            return _create_linked_app(request, app, link_domain, data['name'])
        else:
            return _copy_app_helper(
                request, master_domain, app_id_or_source, link_domain, data['name'], app_id)

    # having login_and_domain_required validates that the user
    # has access to the domain we're copying the app to
    return login_and_domain_required(_inner)(request, form.cleaned_data['domain'], form.cleaned_data)


def _create_linked_app(request, master_app, link_domain, link_app_name):
    master_domain = master_app.domain
    master_version = get_latest_released_app_version(master_domain, master_app._id)
    if not master_version:
        messages.error(request, _("Creating linked app failed."
                                  " Unable to get latest released version of your app."
                                  " Make sure you have at least one released build."))
        return HttpResponseRedirect(reverse_util('app_settings', params={}, args=[master_domain, master_app._id]))

    linked_app = create_linked_app(master_domain, master_app._id, link_domain, link_app_name)
    try:
        update_linked_app(linked_app, request.couch_user.get_id)
    except AppLinkError as e:
        linked_app.delete()
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse_util('app_settings', params={}, args=[master_domain, master_app._id]))

    messages.success(request, _('Application successfully copied and linked.'))
    return HttpResponseRedirect(reverse_util('app_settings', params={}, args=[link_domain, linked_app.get_id]))


def _copy_app_helper(request, master_domain, master_app_id_or_source, copy_to_domain, copy_to_app_name, app_id):
    extra_properties = {'name': copy_to_app_name}
    app_copy = import_app_util(master_app_id_or_source, copy_to_domain, extra_properties, request)
    return back_to_main(request, app_copy.domain, app_id=app_copy._id)


@require_can_edit_apps
def app_from_template(request, domain, slug):
    send_hubspot_form(HUBSPOT_APP_TEMPLATE_FORM_ID, request)
    track_workflow(request.couch_user.username, "User created an application from a template")
    clear_app_cache(request, domain)

    build = load_app_from_slug(domain, request.user.username, slug)
    cloudcare_state = '{{"appId":"{}"}}'.format(build._id)
    return HttpResponseRedirect(reverse(FormplayerMain.urlname, args=[domain]) + '#' + cloudcare_state)


def load_app_from_slug(domain, username, slug):
    # Import app itself
    template = load_app_template(slug)
    app = import_app_util(template, domain, {
        'created_from_template': '%s' % slug,
    })

    # Fetch multimedia, which is hosted elsewhere
    multimedia_filename = os.path.join(app_template_dir(slug), 'multimedia.json')
    if (os.path.exists(multimedia_filename)):
        with open(multimedia_filename) as f:
            path_url_map = json.load(f)
            http = urllib3.PoolManager()
            for path, url in path_url_map.items():
                try:
                    req = http.request('GET', url)
                except Exception:
                    # If anything goes wrong, just bail. It's not a big deal if a template app is missing a file.
                    continue
                if req.status == 200:
                    data = req.data
                    media_class = CommCareMultimedia.get_class_by_data(data)
                    if media_class:
                        multimedia = media_class.get_by_data(data)
                        multimedia.attach_data(data,
                                               original_filename=os.path.basename(path),
                                               username=username)
                        multimedia.add_domain(domain, owner=True)
                        app.create_mapping(multimedia, MULTIMEDIA_PREFIX + path)

    comment = _("A sample application you can try out in Web Apps")
    build = make_async_build_v2(app.get_id, app.domain, app.version, allow_prune=False, comment=comment)
    build.is_released = True
    build.save(increment_version=False)
    return build


@require_can_edit_apps
def export_gzip(req, domain, app_id):
    app_json = get_app(domain, app_id)
    fd, fpath = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as tmp:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr('application.json', app_json.export_json())

    wrapper = FileWrapper(open(fpath, 'rb'))
    response = HttpResponse(wrapper, content_type='application/zip')
    response['Content-Length'] = os.path.getsize(fpath)
    app = Application.get(app_id)
    set_file_download(response, '{domain}-{app_name}-{app_version}.zip'.format(
        app_name=slugify(app.name), app_version=slugify(six.text_type(app.version)), domain=domain
    ))
    return response


@require_can_edit_apps
def import_app(request, domain):
    template = "app_manager/import_app.html"
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

        source = decompress([six.unichr(int(x)) if int(x) < 256 else int(x) for x in compressed.split(',')])
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
                    messages.error(request, "We can't find a project called \"%s\"." % redirect_domain)
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
        })


@require_GET
@require_deploy_apps
def app_settings(request, domain, app_id=None):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id)


@require_GET
@require_deploy_apps
def view_app(request, domain, app_id=None):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, release_manager=True)


@no_conflict_require_POST
@require_can_edit_apps
def new_app(request, domain):
    "Adds an app to the database"
    lang = 'en'
    type = request.POST["type"]
    cls = app_doc_types()[type]
    form_args = []
    if cls == Application:
        app = cls.new_app(domain, "Untitled Application", lang=lang)
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
        response = HttpResponse(json.dumps({'status': 'error', 'message': six.text_type(e)}), status=409)
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
        smart_lang_display: true,
        build: ["es", "hin"]
    }
    """
    app = get_app(domain, app_id)
    try:
        langs, rename = validate_langs(request, app.langs)
    except AssertionError:
        return HttpResponse(status=400)

    # now do it
    for old, new in rename.items():
        if old != new:
            app.rename_lang(old, new)

    #remove deleted languages from build profiles
    new_langs = set(langs)
    deleted = [lang for lang in app.langs if lang not in new_langs]
    for id in app.build_profiles:
        for lang in deleted:
            try:
                app.build_profiles[id].langs.remove(lang)
            except ValueError:
                pass

    def replace_all(list1, list2):
        if list1 != list2:
            while list1:
                list1.pop()
            list1.extend(list2)
    replace_all(app.langs, langs)
    app.smart_lang_display = json.loads(request.body.decode('utf-8'))['smart_lang_display']
    app.save()
    return json_response(langs)


@require_can_edit_apps
@no_conflict_require_POST
def edit_app_ui_translations(request, domain, app_id):
    params = json_request(request.POST)
    lang = params.get('lang')
    translations = params.get('translations')
    app = get_app(domain, app_id)

    # Workaround for https://github.com/dimagi/commcare-hq/pull/10951#issuecomment-203978552
    # auto-fill UI translations might have modules.m0 in the update originating from popular-translations docs
    # since module.m0 is not a UI string, don't update modules.m0 in UI translations
    translations.pop('modules.m0', None)

    app.set_translations(lang, translations)
    app.save(response_json={})  # Updates the app version without updating app properties
    return json_response({})


@require_GET
def get_app_ui_translations(request, domain):
    """
    Retrieves translations from all domains
    """
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
@track_domain_request(calculated_prop='cp_n_saved_app_changes')
def edit_app_attr(request, domain, app_id, attr):
    """
    Called to edit any (supported) app attribute, given by attr

    """
    app = get_app(domain, app_id)

    try:
        hq_settings = json.loads(request.body.decode('utf-8'))['hq']
    except ValueError:
        hq_settings = request.POST

    attributes = [
        'all',
        'recipients', 'name',
        'text_input', 'platform', 'build_spec',
        'use_custom_suite', 'custom_suite',
        'admin_password',
        'comment',
        'use_j2me_endpoint',
        # Application only
        'cloudcare_enabled',
        'case_sharing',
        'translation_strategy',
        'auto_gps_capture',
        # RemoteApp only
        'profile_url',
        'manage_urls',
        'mobile_ucr_restore_version',
    ]
    if attr not in attributes:
        return HttpResponseBadRequest()

    def should_edit(attribute):
        return attribute == attr or ('all' == attr and attribute in hq_settings)

    def parse_sync_interval(interval):
        try:
            return int(interval)
        except ValueError:
            pass

    resp = {"update": {}}
    # For either type of app
    easy_attrs = (
        ('build_spec', BuildSpec.from_string),
        ('practice_mobile_worker_id', None),
        ('case_sharing', None),
        ('cloudcare_enabled', None),
        ('manage_urls', None),
        ('name', None),
        ('platform', None),
        ('recipients', None),
        ('text_input', None),
        ('use_custom_suite', None),
        ('secure_submissions', None),
        ('translation_strategy', None),
        ('auto_gps_capture', None),
        ('use_grid_menus', None),
        ('grid_form_menus', None),
        ('target_commcare_flavor', None),
        ('comment', None),
        ('custom_base_url', None),
        ('use_j2me_endpoint', None),
        ('mobile_ucr_restore_version', None),
        ('location_fixture_restore', None),
    )
    for attribute, transformation in easy_attrs:
        if should_edit(attribute):
            value = hq_settings[attribute]
            if transformation:
                value = transformation(value)
            setattr(app, attribute, value)
            if app.get_doc_type() == 'LinkedApplication' and attribute in app.SUPPORTED_SETTINGS:
                app.linked_app_attrs.update({
                    attribute: value,
                })

    if should_edit("name"):
        clear_app_cache(request, domain)
        name = hq_settings['name']
        resp['update'].update({
            '.variable-app_name': name,
            '[data-id="{id}"]'.format(id=app_id): ApplicationsTab.make_app_title(name, app.doc_type),
        })

    if should_edit("build_spec"):
        resp['update']['commcare-version'] = app.commcare_minor_release

    if should_edit("practice_mobile_worker_id"):
        user_id = hq_settings['practice_mobile_worker_id']
        if not app.enable_practice_users:
            app.practice_mobile_worker_id = None
        elif user_id:
            get_and_assert_practice_user_in_domain(user_id, request.domain)

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
def edit_add_ons(request, domain, app_id):
    app = get_app(domain, app_id)
    current = add_ons.get_dict(request, app)
    for slug, value in six.iteritems(request.POST):
        if slug in current:
            app.add_ons[slug] = value == 'on'
    app.save()
    return HttpResponse(json.dumps({'success': True}))


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
    from_index, to_index = (int(x) for x in (request.POST['from'], request.POST['to']))
    resp = {}
    module_id = None

    try:
        if "forms" == key:
            from_module_uid = request.POST['from_module_uid']
            to_module_uid = request.POST['to_module_uid']
            app.rearrange_forms(from_module_uid, to_module_uid, from_index, to_index)
        elif "modules" == key:
            app.rearrange_modules(from_index, to_index)
    except IncompatibleFormTypeException as e:
        error = "{} {}".format(_('The form is incompatible with the destination menu and was not moved.'), str(e))
        if ajax:
            return json_response({'error': error}, status_code=400)
        messages.error(request, error)
        return back_to_main(request, domain, app_id=app_id, module_id=module_id)
    except (RearrangeError, ModuleNotFoundException):
        error = _(
            'Oops. '
            'Looks like you got out of sync with us. '
            'The sidebar has been updated, so please try again.'
        )
        if ajax:
            return json_response(error, status_code=400)
        messages.error(request, error)
        return back_to_main(request, domain, app_id=app_id, module_id=module_id)
    app.save(resp)
    if ajax:
        return HttpResponse(json.dumps(resp))
    else:
        return back_to_main(request, domain, app_id=app_id, module_id=module_id)


@no_conflict_require_POST
@require_can_edit_apps
def move_child_modules_after_parents(request, domain, app_id):
    app = get_app(domain, app_id)
    app.move_child_modules_after_parents()
    app.save()
    return HttpResponseRedirect(request.META['HTTP_REFERER'])


@require_GET
@require_can_edit_apps
def drop_user_case(request, domain, app_id):
    app = get_app(domain, app_id)
    for module in app.get_modules():
        for form in module.get_forms():
            if form.form_type == 'module_form':
                if 'usercase_update' in form.actions and form.actions['usercase_update'].update:
                    form.actions['usercase_update'].update = {}
                if 'usercase_preload' in form.actions and form.actions['usercase_preload'].preload:
                    form.actions['usercase_preload'].preload = {}
            else:
                for action in list(form.actions.load_update_cases):
                    if action.auto_select and action.auto_select.mode == AUTO_SELECT_USERCASE:
                        form.actions.load_update_cases.remove(action)
    app.save()
    messages.success(
        request,
        _('You have successfully removed User Properties from this application.')
    )
    return back_to_main(request, domain, app_id=app_id)


@require_can_edit_apps
def pull_master_app(request, domain, app_id):
    async_update = request.POST.get('notify') == 'on'
    if async_update:
        update_linked_app_and_notify_task.delay(domain, app_id, request.couch_user.get_id, request.couch_user.email)
        messages.success(request,
                         _('Your request has been submitted. We will notify you via email once completed.'))
    else:
        app = get_current_app(domain, app_id)
        try:
            update_linked_app(app, request.couch_user.get_id)
        except AppLinkError as e:
            messages.error(request, six.text_type(e))
            return HttpResponseRedirect(reverse_util('app_settings', params={}, args=[domain, app_id]))
        messages.success(request, _('Your linked application was successfully updated to the latest version.'))
    track_workflow(request.couch_user.username, "Linked domain: master app pulled")
    return HttpResponseRedirect(reverse_util('app_settings', params={}, args=[domain, app_id]))


@no_conflict_require_POST
@require_can_edit_apps
def update_linked_whitelist(request, domain, app_id):
    app = get_current_app(domain, app_id)
    new_whitelist = json.loads(request.POST.get('whitelist'))
    app.linked_whitelist = new_whitelist
    app.save()
    return HttpResponse()
