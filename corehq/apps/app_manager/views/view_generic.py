from django.http import Http404
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.shortcuts import render
from corehq.apps.app_manager.const import APP_V1

from corehq.apps.app_manager.views.modules import get_module_template, \
    get_module_view_context
from corehq import privileges
from corehq.apps.app_manager.forms import CopyApplicationForm
from corehq.apps.app_manager.views.apps import get_apps_base_context, \
    get_app_view_context
from corehq.apps.app_manager.views.forms import \
    get_form_view_context_and_template
from corehq.apps.app_manager.views.releases import get_releases_context
from corehq.apps.app_manager.views.utils import bail, encode_if_unicode
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
from corehq.apps.app_manager.util import (
    get_all_case_properties,
    get_commcare_versions,
    get_usercase_properties,
    get_app_manager_template,
)
from corehq import toggles
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch.resource_conflict import retry_resource
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    ANDROID_LOGO_PROPERTY_MAPPING,
    ModuleNotFoundException,
)
from django_prbac.utils import has_privilege
from corehq.apps.analytics import ab_tests


@retry_resource(3)
def view_generic(request, domain, app_id=None, module_id=None, form_id=None,
                 copy_app_form=None, release_manager=False):
    """
    This is the main view for the app. All other views redirect to here.

    """
    if form_id and not module_id:
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
        if form_id:
            try:
                form = module.get_form(form_id)
            except IndexError:
                raise Http404()
    except ModuleNotFoundException:
        return bail(request, domain, app_id)

    # Application states that should no longer exist
    if app:
        if app.application_version == APP_V1:
            _assert = soft_assert()
            _assert(False, 'App version 1.0', {'domain': domain, 'app_id': app_id})
            template = get_app_manager_template(
                domain,
                'app_manager/v1/no_longer_supported.html',
                'app_manager/v2/no_longer_supported.html',
            )
            return render(request, template, {
                'domain': domain,
                'app': app,
            })
        if not app.vellum_case_management:
            # Soft assert but then continue rendering; template will contain a user-facing warning
            _assert = soft_assert(['jschweers' + '@' + 'dimagi.com'])
            _assert(False, 'vellum_case_management=False', {'domain': domain, 'app_id': app_id})

    context = get_apps_base_context(request, domain, app)
    if app and app.copy_of:
        # don't fail hard.
        return HttpResponseRedirect(reverse(
            "view_app", args=[domain, app.copy_of] # TODO - is this right?
        ))

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

    lang = context['lang']
    if app and not module and hasattr(app, 'translations'):
        context.update({"translations": app.translations.get(lang, {})})

    if form:
        template, form_context = get_form_view_context_and_template(
            request, domain, form, context['langs']
        )
        context.update({
            'case_properties': get_all_case_properties(app),
            'usercase_properties': get_usercase_properties(app),
        })

        context.update(form_context)
    elif module:
        template = get_module_template(domain, module)
        # make sure all modules have unique ids
        app.ensure_module_unique_ids(should_save=True)
        module_context = get_module_view_context(app, module, lang)
        context.update(module_context)
    elif app:
        context.update(get_app_view_context(request, app))

        v2_template = ('app_manager/v2/app_view_release_manager.html'
                       if release_manager
                       else 'app_manager/v2/app_view_settings.html')

        template = get_app_manager_template(
            domain,
            'app_manager/v1/app_view.html',
            v2_template
        )

        if release_manager:
            context.update(get_releases_context(request, domain, app_id))
        context.update({
            'is_app_settings_page': not release_manager,
        })
    else:
        from corehq.apps.dashboard.views import NewUserDashboardView
        if toggles.APP_MANAGER_V2.enabled(domain):
            context.update(NewUserDashboardView.get_page_context(domain))
            template = NewUserDashboardView.template_name
        else:
            return HttpResponseRedirect(reverse(NewUserDashboardView.urlname, args=[domain]))

    # update multimedia context for forms and modules.
    menu_host = form or module
    if menu_host:
        default_file_name = 'module%s' % module_id
        if form_id:
            default_file_name = '%s_form%s' % (default_file_name, form_id)

        specific_media = {
            'menu': {
                'menu_refs': app.get_menu_media(
                    module, module_id, form=form, form_index=form_id, to_language=lang
                ),
                'default_file_name': '{name}_{lang}'.format(name=default_file_name, lang=lang),
            }
        }

        if module and module.uses_media():
            def _make_name(suffix):
                return "{default_name}_{suffix}_{lang}".format(
                    default_name=default_file_name,
                    suffix=suffix,
                    lang=lang,
                )

            specific_media['case_list_form'] = {
                'menu_refs': app.get_case_list_form_media(module, module_id, to_language=lang),
                'default_file_name': _make_name('case_list_form'),
            }
            specific_media['case_list_menu_item'] = {
                'menu_refs': app.get_case_list_menu_item_media(module, module_id, to_language=lang),
                'default_file_name': _make_name('case_list_menu_item'),
            }
            specific_media['case_list_lookup'] = {
                'menu_refs': app.get_case_list_lookup_image(module, module_id),
                'default_file_name': '{}_case_list_lookup'.format(default_file_name),
            }

            if hasattr(module, 'product_details'):
                specific_media['product_list_lookup'] = {
                    'menu_refs': app.get_case_list_lookup_image(module, module_id, type='product'),
                    'default_file_name': '{}_product_list_lookup'.format(default_file_name),
                }

        context.update({
            'multimedia': {
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
        try:
            context['multimedia']['references'] = app.get_references()
        except ReportConfigurationNotFoundError:
            pass
        context['multimedia'].update(specific_media)

    error = request.GET.get('error', '')

    context.update({
        'error': error,
        'app': app,
    })

    # Pass form for Copy Application to template
    domain_names = [d.name for d in Domain.active_for_user(request.couch_user)]
    domain_names.sort()
    if app and copy_app_form is None:
        toggle_enabled = toggles.EXPORT_ZIPPED_APPS.enabled(request.user.username)
        copy_app_form = CopyApplicationForm(domain, app_id, export_zipped_apps_enabled=toggle_enabled)
        context.update({
            'domain_names': domain_names,
        })
    linked_apps_enabled = toggles.LINKED_APPS.enabled(domain)
    context.update({
        'copy_app_form': copy_app_form,
        'linked_apps_enabled': linked_apps_enabled,
    })

    context['latest_commcare_version'] = get_commcare_versions(request.user)[-1]

    if app and app.doc_type == 'Application' and has_privilege(request, privileges.COMMCARE_LOGO_UPLOADER):
        uploader_slugs = ANDROID_LOGO_PROPERTY_MAPPING.keys()
        from corehq.apps.hqmedia.controller import MultimediaLogoUploadController
        from corehq.apps.hqmedia.views import ProcessLogoFileUploadView
        context.update({
            "sessionid": request.COOKIES.get('sessionid'),
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

    live_preview_ab = ab_tests.ABTest(ab_tests.LIVE_PREVIEW, request)
    domain_obj = Domain.get_by_name(domain)
    context.update({
        'live_preview_ab': live_preview_ab.context,
        'is_onboarding_domain': domain_obj.is_onboarding_domain,
        'show_live_preview': (
            toggles.PREVIEW_APP.enabled(domain)
            or toggles.PREVIEW_APP.enabled(request.couch_user.username)
            or (domain_obj.is_onboarding_domain and live_preview_ab.version == ab_tests.LIVE_PREVIEW_ENABLED)
        )
    })

    response = render(request, template, context)

    live_preview_ab.update_response(response)
    response.set_cookie('lang', encode_if_unicode(lang))
    return response
