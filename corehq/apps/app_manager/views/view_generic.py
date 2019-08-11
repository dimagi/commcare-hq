from __future__ import absolute_import
from __future__ import unicode_literals
from django.http import Http404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render
from corehq.apps.app_manager.const import APP_V1
from corehq.apps.app_manager.exceptions import FormNotFoundException

from corehq.apps.app_manager.views.modules import get_module_template, \
    get_module_view_context
from corehq import privileges
from corehq.apps.app_manager.forms import CopyApplicationForm
from corehq.apps.app_manager import add_ons
from corehq.apps.app_manager.views.apps import get_apps_base_context, \
    get_app_view_context
from corehq.apps.app_manager.views.forms import \
    get_form_view_context_and_template
from corehq.apps.app_manager.views.releases import get_releases_context
from corehq.apps.app_manager.views.utils import bail, set_lang_cookie
from corehq.apps.hqmedia.controller import (
    MultimediaImageUploadController,
    MultimediaAudioUploadController,
)
from corehq.apps.domain.models import Domain
from corehq.apps.hqmedia.models import (
    ApplicationMediaReference,
    CommCareImage,
)
from corehq.apps.hqmedia.views import (
    ProcessImageFileUploadView,
    ProcessAudioFileUploadView,
)
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link, is_linked_domain
from corehq.apps.app_manager.util import get_commcare_versions, is_remote_app
from corehq import toggles
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.apps.cloudcare.utils import should_show_preview_app
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch.resource_conflict import retry_resource
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    ANDROID_LOGO_PROPERTY_MAPPING,
    ModuleNotFoundException,
    ReportModule,
    CustomIcon)
from django_prbac.utils import has_privilege
import six


@retry_resource(3)
def view_generic(request, domain, app_id, module_id=None, form_id=None,
                 copy_app_form=None, release_manager=False,
                 module_unique_id=None, form_unique_id=None):
    """
    This is the main view for the app. All other views redirect to here.

    """
    if form_id and not module_id and module_unique_id is None:
        return bail(request, domain, app_id)

    app = module = form = None
    try:
        if app_id:
            app = get_app(domain, app_id)

        if module_id:
            try:
                module = app.get_module(module_id)
            except ModuleNotFoundException:
                raise Http404()
            if not module.unique_id:
                module.get_or_create_unique_id()
                app.save()
        elif module_unique_id:
            try:
                module = app.get_module_by_unique_id(module_unique_id)
            except ModuleNotFoundException:
                raise Http404()
            module_id = module.id

        if form_id and module is not None:
            try:
                form = module.get_form(form_id)
            except IndexError:
                raise Http404()
        elif form_unique_id:
            try:
                form = app.get_form(form_unique_id)
            except FormNotFoundException:
                raise Http404()
            form_id = form.id

        if form is not None and module is None:
            # this is the case where only the form_unique_id is given
            module = form.get_module()
            module_id = module.id

    except (ModuleNotFoundException, FormNotFoundException):
        return bail(request, domain, app_id)

    # Application states that should no longer exist
    if app:
        if app.application_version == APP_V1:
            _assert = soft_assert()
            _assert(False, 'App version 1.0', {'domain': domain, 'app_id': app_id})
            return render(request, "app_manager/no_longer_supported.html", {
                'domain': domain,
                'app': app,
            })
        if not app.vellum_case_management and not app.is_remote_app():
            # Soft assert but then continue rendering; template will contain a user-facing warning
            _assert = soft_assert(['jschweers' + '@' + 'dimagi.com'])
            _assert(False, 'vellum_case_management=False', {'domain': domain, 'app_id': app_id})
        if (form is not None and "usercase_preload" in getattr(form, "actions", {})
                and form.actions.usercase_preload.preload):
            _assert = soft_assert(['dmiller' + '@' + 'dimagi.com'])
            _assert(False, 'User property easy refs + old-style config = bad', {
                'domain': domain,
                'app_id': app_id,
                'module_id': module_id,
                'module_unique_id': module_unique_id,
                'form_id': form_id,
                'form_unique_id': form_unique_id,
            })

    context = get_apps_base_context(request, domain, app)
    if app and app.copy_of:
        # redirect to "main" app rather than specific build
        return HttpResponseRedirect(reverse(
            "view_app", args=[domain, app.copy_of]
        ))

    context.update({
        'module': module,
        'form': form,
    })

    lang = context['lang']
    if app and not module and hasattr(app, 'translations'):
        context.update({"translations": app.translations.get(lang, {})})

    if app and not app.is_remote_app():
        context.update({
            'add_ons': add_ons.get_dict(request, app, module, form),
            'add_ons_layout': add_ons.get_layout(request),
        })

    if form:
        template, form_context = get_form_view_context_and_template(
            request, domain, form, context['langs'], current_lang=lang
        )
        context.update(form_context)
    elif module:
        template = get_module_template(request.user, module)
        # make sure all modules have unique ids
        app.ensure_module_unique_ids(should_save=True)
        module_context = get_module_view_context(request, app, module, lang)
        context.update(module_context)
    elif app:
        context.update(get_app_view_context(request, app))

        template = 'app_manager/app_view_settings.html'
        if release_manager:
            template = 'app_manager/app_view_release_manager.html'
        if release_manager:
            context.update(get_releases_context(request, domain, app_id))
        context.update({
            'is_app_settings_page': not release_manager,
        })
    else:
        from corehq.apps.dashboard.views import DomainDashboardView
        return HttpResponseRedirect(reverse(DomainDashboardView.urlname, args=[domain]))

    # update multimedia context for forms and modules.
    menu_host = form or module
    if menu_host:
        default_file_name = 'module%s' % module_id
        if form:
            default_file_name = '%s_form%s' % (default_file_name, form_id)

        specific_media = [{
            'menu_refs': app.get_menu_media(
                module, module_id, form=form, form_index=form_id, to_language=lang
            ),
            'default_file_name': '{name}_{lang}'.format(name=default_file_name, lang=lang),
        }]

        if not form and module and not isinstance(module, ReportModule) and module.uses_media():
            def _make_name(suffix):
                return "{default_name}_{suffix}_{lang}".format(
                    default_name=default_file_name,
                    suffix=suffix,
                    lang=lang,
                )

            specific_media.append({
                'menu_refs': app.get_case_list_form_media(module, module_id, to_language=lang),
                'default_file_name': _make_name('case_list_form'),
                'qualifier': 'case_list_form_',
            })
            specific_media.append({
                'menu_refs': app.get_case_list_menu_item_media(module, module_id, to_language=lang),
                'default_file_name': _make_name('case_list_menu_item'),
                'qualifier': 'case_list-menu_item_',
            })
            if (toggles.CASE_LIST_LOOKUP.enabled(request.user.username) or
                    toggles.CASE_LIST_LOOKUP.enabled(app.domain) or
                    toggles.BIOMETRIC_INTEGRATION.enabled(app.domain)):
                specific_media.append({
                    'menu_refs': app.get_case_list_lookup_image(module, module_id),
                    'default_file_name': '{}_case_list_lookup'.format(default_file_name),
                    'qualifier': 'case-list-lookupcase',
                })

                if hasattr(module, 'product_details'):
                    specific_media.append({
                        'menu_refs': app.get_case_list_lookup_image(module, module_id, type='product'),
                        'default_file_name': '{}_product_list_lookup'.format(default_file_name),
                        'qualifier': 'case-list-lookupproduct',
                    })

        uploaders = {
            'icon': MultimediaImageUploadController(
                "hqimage",
                reverse(ProcessImageFileUploadView.urlname,
                        args=[app.domain, app.get_id])
            ),
            'audio': MultimediaAudioUploadController(
                "hqaudio", reverse(ProcessAudioFileUploadView.urlname,
                        args=[app.domain, app.get_id])
            ),
        }
        context.update({
            'multimedia': {
                "object_map": app.get_object_map(),
                'upload_managers': uploaders,
                'upload_managers_js': {type: u.js_options for type, u in six.iteritems(uploaders)},
            }
        })
        context['module_icon'] = None
        if toggles.CUSTOM_ICON_BADGES.enabled(domain):
            context['module_icon'] = module.custom_icon if module.custom_icon else CustomIcon()
        try:
            context['multimedia']['references'] = app.get_references()
        except ReportConfigurationNotFoundError:
            pass
        context['nav_menu_media_specifics'] = specific_media

    error = request.GET.get('error', '')

    context.update({
        'error': error,
        'app': app,
    })

    # Pass form for Copy Application to template
    domain_names = [
        d.name for d in Domain.active_for_user(request.couch_user)
        if not (is_linked_domain(request.domain)
                and get_domain_master_link(request.domain).master_domain == d.name)
    ]
    domain_names.sort()
    if app and copy_app_form is None:
        copy_app_form = CopyApplicationForm(domain, app)
        context.update({
            'domain_names': domain_names,
        })
    linked_domains_enabled = toggles.LINKED_DOMAINS.enabled(domain)
    context.update({
        'copy_app_form': copy_app_form,
        'linked_domains_enabled': linked_domains_enabled,
    })

    context['latest_commcare_version'] = get_commcare_versions(request.user)[-1]

    if app and not is_remote_app(app) and has_privilege(request, privileges.COMMCARE_LOGO_UPLOADER):
        uploader_slugs = list(ANDROID_LOGO_PROPERTY_MAPPING.keys())
        from corehq.apps.hqmedia.controller import MultimediaLogoUploadController
        from corehq.apps.hqmedia.views import ProcessLogoFileUploadView
        uploaders = [
            MultimediaLogoUploadController(
                slug,
                reverse(
                    ProcessLogoFileUploadView.urlname,
                    args=[domain, app_id, slug],
                )
            )
            for slug in uploader_slugs
        ]
        context.update({
            "sessionid": request.COOKIES.get('sessionid'),
            "uploaders": uploaders,
            "uploaders_js": [u.js_options for u in uploaders],
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

    context.update({
        'show_live_preview': app and should_show_preview_app(
            request,
            app,
            request.couch_user.username
        ),
        'can_preview_form': request.couch_user.has_permission(domain, 'edit_data')
    })

    confirm = request.session.pop('CONFIRM', False)
    context.update({'confirm': confirm})

    response = render(request, template, context)

    set_lang_cookie(response, lang)
    return response
