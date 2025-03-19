from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from django_prbac.utils import has_privilege

from dimagi.utils.couch.resource_conflict import retry_resource

from corehq import privileges, toggles
from corehq.apps.app_manager import add_ons
from corehq.apps.app_manager.const import APP_V1
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.app_manager.forms import CopyApplicationForm
from corehq.apps.app_manager.models import (
    ANDROID_LOGO_PROPERTY_MAPPING,
    CustomIcon,
    ModuleNotFoundException,
    ReportModule,
)
from corehq.apps.app_manager.util import get_commcare_versions, is_remote_app
from corehq.apps.app_manager.views.apps import (
    get_app_view_context,
    get_apps_base_context,
)
from corehq.apps.app_manager.views.forms import (
    get_form_view_context,
)
from corehq.apps.app_manager.views.modules import (
    get_module_template,
    get_module_view_context,
)
from corehq.apps.app_manager.views.releases import get_releases_context
from corehq.apps.app_manager.views.utils import bail, set_lang_cookie
from corehq.apps.cloudcare.utils import should_show_preview_app
from corehq.apps.domain.models import AppReleaseModeSetting, Domain
from corehq.apps.hqmedia.controller import (
    MultimediaAudioUploadController,
    MultimediaImageUploadController,
)
from corehq.apps.hqmedia.models import ApplicationMediaReference, CommCareImage
from corehq.apps.hqmedia.views import (
    ProcessAudioFileUploadView,
    ProcessImageFileUploadView,
)
from corehq.apps.linked_domain.dbaccessors import (
    get_accessible_downstream_domains,
    get_upstream_domain_link,
    is_active_downstream_domain,
)
from corehq.apps.linked_domain.util import can_domain_access_linked_domains
from corehq.util.soft_assert import soft_assert


@retry_resource(3)
def view_generic(
    request,
    domain,
    app_id,
    module_id=None,
    form_id=None,
    copy_app_form=None,
    release_manager=False,
    module_unique_id=None,
    form_unique_id=None,
):
    """
    This is the main view for the app. All other views redirect to here.
    """
    if form_id and not module_id and module_unique_id is None:
        return bail(request, domain, app_id)

    app = get_app(domain, app_id)
    module, form = _get_module_and_form(
        app, module_id, form_id, module_unique_id, form_unique_id
    )
    bad_state_response = _handle_bad_states(
        request,
        domain,
        app_id,
        app,
        module,
        form,
        module_unique_id,
        form_unique_id,
    )
    if bad_state_response:
        return bad_state_response

    if app.copy_of:
        # redirect to "main" app rather than specific build
        return HttpResponseRedirect(reverse(
            "view_app", args=[domain, app.copy_of]
        ))

    if copy_app_form is None:
        copy_app_form = CopyApplicationForm(domain, app)

    context = get_apps_base_context(request, domain, app)
    context.update({
        'module': module,
        'form': form,
    })

    lang = context['lang']
    if not module and hasattr(app, 'translations'):
        context["translations"] = app.translations.get(lang, {})

    if not app.is_remote_app():
        context.update({
            'add_ons': add_ons.get_dict(request, app, module, form),
            'add_ons_privileges': add_ons.get_privileges_dict(request),
            'add_ons_layout': add_ons.get_layout(request),
        })

    if form:
        template = "app_manager/form_view.html"
        context.update(get_form_view_context(
            request,
            domain,
            form,
            langs=context['langs'],
            current_lang=lang,
        ))
    elif module:
        template = get_module_template(request.user, module)
        context.update(get_module_view_context(request, app, module, lang))
    else:
        template = 'app_manager/app_view_settings.html'
        context.update(get_app_view_context(request, app))

        if release_manager:
            template = 'app_manager/app_view_release_manager.html'
            context.update(get_releases_context(request, domain, app_id))

        context['is_app_settings_page'] = not release_manager

    if form or module:
        context.update(_get_multimedia_context(
            request.user.username,
            domain,
            app,
            module,
            form,
            lang,
        ))

    context.update(_get_domain_context(
        domain,
        request.domain,
        request.couch_user,
    ))

    if (
        not is_remote_app(app)
        and has_privilege(request, privileges.COMMCARE_LOGO_UPLOADER)
    ):
        context.update(_get_logo_uploader_context(domain, app_id, app))

    context.update({
        'error': request.GET.get('error', ''),
        'confirm': request.session.pop('CONFIRM', False),
        'copy_app_form': copy_app_form,
        'latest_commcare_version': get_commcare_versions(request.user)[-1],
        'show_live_preview': should_show_preview_app(
            request,
            app,
            request.couch_user.username
        ),
        'show_release_mode':
            AppReleaseModeSetting.get_settings(domain).is_visible
    })

    response = render(request, template, context)
    set_lang_cookie(response, lang)
    return response


def _get_module_and_form(
    app,
    module_id,
    form_id,
    module_unique_id,
    form_unique_id,
):
    module = form = None

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

    if form is not None and module is None:
        # this is the case where only the form_unique_id is given
        module = form.get_module()

    return module, form


def _handle_bad_states(
    request,
    domain,
    app_id,
    app,
    module,
    form,
    module_unique_id,
    form_unique_id,
):
    # Application states that should no longer exist
    if app.application_version == APP_V1:
        _assert = soft_assert()
        _assert(False, 'App version 1.0', {'domain': domain, 'app_id': app_id})
        return render(request, "app_manager/no_longer_supported.html", {
            'domain': domain,
            'app': app,
        })

    if (
        form is not None
        and "usercase_preload" in getattr(form, "actions", {})
        and form.actions.usercase_preload.preload
    ):
        _assert = soft_assert(['dmiller' + '@' + 'dimagi.com'])
        _assert(False, 'User property easy refs + old-style config = bad', {
            'domain': domain,
            'app_id': app_id,
            'module_id': module.id,
            'module_unique_id': module_unique_id,
            'form_id': form.id,
            'form_unique_id': form_unique_id,
        })


def _get_multimedia_context(
    username,
    domain,
    app,
    module,
    form,
    lang,
):
    """
    Returns multimedia context for forms and modules.
    """
    multimedia_context = {}
    uploaders = {
        'icon': MultimediaImageUploadController(
            "hqimage",
            reverse(ProcessImageFileUploadView.urlname,
                    args=[app.domain, app.get_id])
        ),
        'audio': MultimediaAudioUploadController(
            "hqaudio",
            reverse(ProcessAudioFileUploadView.urlname,
                    args=[app.domain, app.get_id])
        ),
    }
    multimedia_map = app.multimedia_map
    if form or module:
        multimedia_map = (form or module).get_relevant_multimedia_map(app)
    multimedia_context.update({
        'multimedia': {
            "object_map": app.get_object_map(multimedia_map=multimedia_map),
            'upload_managers': uploaders,
            'upload_managers_js': {
                type_: u.js_options for type_, u in uploaders.items()
            },
        }
    })

    if toggles.CUSTOM_ICON_BADGES.enabled(domain):
        if module.custom_icon:
            multimedia_context['module_icon'] = module.custom_icon
        else:
            multimedia_context['module_icon'] = CustomIcon()
    else:
        multimedia_context['module_icon'] = None

    multimedia_context['nav_menu_media_specifics'] = _get_specific_media(
        username,
        domain,
        app,
        module,
        form,
        lang,
    )
    return multimedia_context


def _get_specific_media(
    username,
    domain,
    app,
    module,
    form,
    lang,
):
    module_id = module.id if module else None
    form_id = form.id if form else None
    default_file_name = f'module{module_id}'
    if form:
        default_file_name = f'{default_file_name}_form{form_id}'

    specific_media = [{
        'menu_refs': app.get_menu_media(
            module,
            form=form,
            form_index=form_id,
            to_language=lang,
        ),
        'default_file_name': f'{default_file_name}_{lang}',
    }]

    if (
        not form
        and module
        and not isinstance(module, ReportModule)
        and module.uses_media()
    ):
        specific_media.append({
            'menu_refs': app.get_case_list_form_media(
                module,
                to_language=lang,
            ),
            'default_file_name': _make_file_name(
                default_file_name,
                'case_list_form',
                lang,
            ),
            'qualifier': 'case_list_form_',
        })
        specific_media.append({
            'menu_refs': app.get_case_list_menu_item_media(
                module,
                to_language=lang,
            ),
            'default_file_name': _make_file_name(
                default_file_name,
                'case_list_menu_item',
                lang,
            ),
            'qualifier': 'case_list-menu_item_',
        })
        if (
            module
            and hasattr(module, 'search_config')
            and module.uses_media()
            and toggles.USH_CASE_CLAIM_UPDATES.enabled(domain)
        ):
            specific_media.extend([
                {
                    'menu_refs': app.get_case_search_label_media(
                        module,
                        module.search_config.search_label,
                        to_language=lang,
                    ),
                    'default_file_name': _make_file_name(
                        default_file_name,
                        'case_search_label_item',
                        lang,
                    ),
                    'qualifier': 'case_search-search_label_media_'
                },
                {
                    'menu_refs': app.get_case_search_label_media(
                        module,
                        module.search_config.search_again_label,
                        to_language=lang,
                    ),
                    'default_file_name': _make_file_name(
                        default_file_name,
                        'case_search_again_label_item',
                        lang,
                    ),
                    'qualifier': 'case_search-search_again_label_media_'
                }
            ])

        if (
            toggles.CASE_LIST_LOOKUP.enabled(username)
            or toggles.CASE_LIST_LOOKUP.enabled(app.domain)
            or toggles.BIOMETRIC_INTEGRATION.enabled(app.domain)
        ):
            specific_media.append({
                'menu_refs': app.get_case_list_lookup_image(module),
                'default_file_name': f'{default_file_name}_case_list_lookup',
                'qualifier': 'case-list-lookupcase',
            })

            if hasattr(module, 'product_details'):
                specific_media.append({
                    'menu_refs': app.get_case_list_lookup_image(
                        module,
                        type='product',
                    ),
                    'default_file_name':
                        f'{default_file_name}_product_list_lookup',
                    'qualifier': 'case-list-lookupproduct',
                })
    return specific_media


def _get_domain_context(domain, request_domain, couch_user):
    domain_names = {
        d.name for d in Domain.active_for_user(couch_user)
        if not (
            is_active_downstream_domain(request_domain)
            and get_upstream_domain_link(request_domain).master_domain == d.name
        )
    }
    domain_names.add(request_domain)
    # NOTE: The CopyApplicationForm checks for access to linked domains
    #       before displaying
    linkable_domains = []
    limit_to_linked_domains = True
    if can_domain_access_linked_domains(request_domain):
        linkable_domains = get_accessible_downstream_domains(
            domain,
            couch_user,
        )
        limit_to_linked_domains = not couch_user.is_superuser
    return {
        'domain_names': sorted(domain_names),
        'linkable_domains': sorted(linkable_domains),
        'limit_to_linked_domains': limit_to_linked_domains,
    }


def _get_logo_uploader_context(domain, app_id, app):
    from corehq.apps.hqmedia.controller import (
        MultimediaLogoUploadController,
    )
    from corehq.apps.hqmedia.views import ProcessLogoFileUploadView

    uploader_slugs = list(ANDROID_LOGO_PROPERTY_MAPPING.keys())
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
    return {
        "uploaders": uploaders,
        "uploaders_js": [u.js_options for u in uploaders],
        "refs": {
            slug: ApplicationMediaReference(
                app.logo_refs.get(slug, {}).get("path", slug),
                media_class=CommCareImage,
            ).as_dict()
            for slug in uploader_slugs
        },
        "media_info": {
            slug: app.logo_refs.get(slug)
            for slug in uploader_slugs if app.logo_refs.get(slug)
        },
    }


def _make_file_name(default_name, suffix, lang):
    """
    Appends ``suffix`` and ``lang`` to ``default_name``

    >>> _make_file_name('sir_lancelot', 'obe', 'fr')
    'sir_lancelot_obe_fr'

    """
    return f'{default_name}_{suffix}_{lang}'
