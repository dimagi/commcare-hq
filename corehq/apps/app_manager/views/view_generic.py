from django.http import Http404
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.shortcuts import render

from corehq.apps.app_manager.views.modules import get_module_template, \
    get_module_view_context
from corehq import privileges
from corehq.apps.app_manager.forms import CopyApplicationForm
from corehq.apps.app_manager.views.apps import get_apps_base_context, \
    get_app_view_context
from corehq.apps.app_manager.views.forms import \
    get_form_view_context_and_template
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
)
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch.resource_conflict import retry_resource
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    ANDROID_LOGO_PROPERTY_MAPPING,
    ModuleNotFoundException,
)
from django_prbac.utils import has_privilege


@retry_resource(3)
def view_generic(request, domain, app_id=None, module_id=None, form_id=None,
                 copy_app_form=None):
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

    if app and app.application_version == '1.0':
        _assert = soft_assert(to=['droberts' + '@' + 'dimagi.com'])
        _assert(False, 'App version 1.0', {'domain': domain, 'app_id': app_id})
        return render(request, 'app_manager/no_longer_supported.html', {
            'domain': domain,
            'app': app,
        })

    context = get_apps_base_context(request, domain, app)
    if app and app.copy_of:
        # don't fail hard.
        return HttpResponseRedirect(reverse(
            "corehq.apps.app_manager.views.view_app", args=[domain, app.copy_of]
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
        template = get_module_template(module)
        # make sure all modules have unique ids
        app.ensure_module_unique_ids(should_save=True)
        module_context = get_module_view_context(app, module, lang)
        context.update(module_context)
    elif app:
        template = "app_manager/app_view.html"
        context.update(get_app_view_context(request, app))
    else:
        from corehq.apps.dashboard.views import NewUserDashboardView
        template = NewUserDashboardView.template_name
        context.update({'templates': NewUserDashboardView.templates(domain)})

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
    context.update({
        'copy_app_form': copy_app_form if copy_app_form is not None else CopyApplicationForm(app_id),
        'domain_names': domain_names,
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

    response = render(request, template, context)

    response.set_cookie('lang', encode_if_unicode(lang))
    return response
