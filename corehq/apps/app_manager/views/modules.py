# coding=utf-8
from __future__ import absolute_import

from __future__ import unicode_literals

import uuid
from collections import OrderedDict
import json
import logging
from distutils.version import LooseVersion

from django.utils.safestring import mark_safe
from lxml import etree

from django.template.loader import render_to_string
from django.utils.translation import ugettext as _, gettext_lazy
from django.http import HttpResponse, Http404, HttpResponseBadRequest, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_GET
from django.contrib import messages

from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.app_schemas.case_properties import ParentCasePropertyBuilder
from corehq.apps.app_manager import add_ons
from corehq.apps.app_manager.views.media_utils import process_media_attribute, \
    handle_media_edits
from corehq.apps.case_search.models import case_search_enabled_for_domain
from corehq.apps.domain.decorators import track_domain_request, LoginAndDomainMixin
from corehq.apps.domain.models import Domain
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from corehq.apps.reports.daterange import get_simple_dateranges

from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.views.utils import back_to_main, bail, get_langs, handle_custom_icon_edits, \
    clear_xmlns_app_id_cache
from corehq import toggles
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.const import (
    MOBILE_UCR_VERSION_1,
    USERCASE_TYPE,
    CLAIM_DEFAULT_RELEVANT_CONDITION,
)
from corehq.apps.app_manager.util import (
    is_valid_case_type,
    is_usercase_in_use,
    prefix_usercase_properties,
    module_offers_search,
    module_case_hierarchy_has_circular_reference)
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.hqmedia.controller import MultimediaHTMLUploadController
from corehq.apps.hqmedia.models import ApplicationMediaReference, CommCareMultimedia
from corehq.apps.hqmedia.views import ProcessDetailPrintTemplateUploadView
from corehq.apps.userreports.models import ReportConfiguration, \
    StaticReportConfiguration
from dimagi.utils.web import json_response, json_request
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    AdvancedModule,
    CaseSearch,
    CaseSearchProperty,
    DeleteModuleRecord,
    DetailColumn,
    DetailTab,
    FormActionCondition,
    MappingItem,
    Module,
    ModuleNotFoundException,
    OpenCaseAction,
    ParentSelect,
    ReportModule,
    ShadowModule,
    SortElement,
    ReportAppConfig,
    UpdateCaseAction,
    FixtureSelect,
    DefaultCaseSearchProperty,
    get_all_mobile_filter_configs,
    get_auto_filter_configurations,
    CaseListForm,
)
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps
from corehq.apps.app_manager.suite_xml.features.mobile_ucr import get_uuids_by_instance_id
from six.moves import map

logger = logging.getLogger(__name__)


def get_module_template(user, module):
    if isinstance(module, AdvancedModule):
        return "app_manager/module_view_advanced.html"
    elif isinstance(module, ReportModule):
        return "app_manager/module_view_report.html"
    else:
        return "app_manager/module_view.html"


def get_module_view_context(app, module, lang=None):
    # shared context
    context = {
        'edit_name_url': reverse('edit_module_attr', args=[app.domain, app.id, module.unique_id, 'name']),
    }
    module_brief = {
        'id': module.id,
        'case_type': module.case_type,
        'lang': lang,
        'langs': app.langs,
        'module_type': module.module_type,
        'name_enum': module.name_enum,
        'requires_case_details': module.requires_case_details(),
        'unique_id': module.unique_id,
    }
    case_property_builder = _setup_case_property_builder(app)
    if isinstance(module, AdvancedModule):
        module_brief.update({
            'auto_select_case': module.auto_select_case,
            'has_schedule': module.has_schedule,
        })
        context.update(_get_shared_module_view_context(app, module, case_property_builder, lang))
        context.update(_get_advanced_module_view_context(app, module))
    elif isinstance(module, ReportModule):
        context.update(_get_report_module_context(app, module))
    else:
        context.update(_get_shared_module_view_context(app, module, case_property_builder, lang))
        context.update(_get_basic_module_view_context(app, module, case_property_builder))
    if isinstance(module, ShadowModule):
        context.update(_get_shadow_module_view_context(app, module, lang))
    context.update({'module_brief': module_brief})
    return context


def _get_shared_module_view_context(app, module, case_property_builder, lang=None):
    '''
    Get context items that are used by both basic and advanced modules.
    '''
    case_type = module.case_type
    context = {
        'details': _get_module_details_context(app, module, case_property_builder, case_type),
        'case_list_form_options': _case_list_form_options(app, module, case_type, lang),
        'valid_parents_for_child_module': _get_valid_parents_for_child_module(app, module),
        'js_options': {
            'fixture_columns_by_type': _get_fixture_columns_by_type(app.domain),
            'is_search_enabled': case_search_enabled_for_domain(app.domain),
            'search_properties': module.search_config.properties if module_offers_search(module) else [],
            'include_closed': module.search_config.include_closed if module_offers_search(module) else False,
            'default_properties': module.search_config.default_properties if module_offers_search(module) else [],
            'search_button_display_condition':
                module.search_config.search_button_display_condition if module_offers_search(module) else "",
            'blacklisted_owner_ids_expression': (
                module.search_config.blacklisted_owner_ids_expression if module_offers_search(module) else ""),
        },
    }
    if toggles.CASE_DETAIL_PRINT.enabled(app.domain):
        slug = 'module_%s_detail_print' % module.unique_id
        print_template = module.case_details.long.print_template
        print_uploader = MultimediaHTMLUploadController(
            slug,
            reverse(
                ProcessDetailPrintTemplateUploadView.urlname,
                args=[app.domain, app.id, module.unique_id],
            )
        )
        if not print_template:
            print_template = {
                'path': 'jr://file/commcare/text/%s.html' % slug,
            }
        context.update({
            'print_uploader': print_uploader,
            'print_uploader_js': print_uploader.js_options,
            'print_ref': ApplicationMediaReference(
                print_template.get('path'),
                media_class=CommCareMultimedia,
            ).as_dict(),
            'print_media_info': print_template,
        })
    return context


def _get_advanced_module_view_context(app, module):
    case_type = module.case_type
    return {
        'case_list_form_not_allowed_reasons': _case_list_form_not_allowed_reasons(module),
        'child_module_enabled': True,
        'schedule_phases': [
            {
                'id': schedule.id,
                'anchor': schedule.anchor,
                'forms': [
                    form.schedule_form_id for form in schedule.get_forms()
                ],
            } for schedule in module.get_schedule_phases()
        ],
    }


def _get_basic_module_view_context(app, module, case_property_builder):
    return {
        'parent_case_modules': _get_modules_with_parent_case_type(
            app, module, case_property_builder, module.case_type),
        'case_list_form_not_allowed_reasons': _case_list_form_not_allowed_reasons(module),
        'child_module_enabled': (
            toggles.BASIC_CHILD_MODULE.enabled(app.domain) and not module.is_training_module
        ),
    }


def _get_shadow_module_view_context(app, module, lang=None):
    langs = None if lang is None else [lang]

    def get_mod_dict(mod):
        return {
            'unique_id': mod.unique_id,
            'name': trans(mod.name, langs),
            'root_module_id': mod.root_module_id,
            'forms': [{'unique_id': f.unique_id, 'name': trans(f.name, langs)} for f in mod.get_forms()]
        }

    return {
        'case_list_form_not_allowed_reasons': _case_list_form_not_allowed_reasons(module),
        'shadow_module_options': {
            'modules': [get_mod_dict(m) for m in app.modules if m.module_type in ['basic', 'advanced']],
            'source_module_id': module.source_module_id,
            'excluded_form_ids': module.excluded_form_ids,
        },
    }


def _get_report_module_context(app, module):
    def _report_to_config(report):
        return {
            'report_id': report._id,
            'title': report.title,
            'description': report.description,
            'charts': [chart for chart in report.charts if
                       chart.type == 'multibar'],
            'filter_structure': report.filters_without_prefilters,
        }

    all_reports = ReportConfiguration.by_domain(app.domain) + \
                  StaticReportConfiguration.by_domain(app.domain)
    validity = module.check_report_validity()

    # We're now proactively deleting these references, so after that's been
    # out for a while, this can be removed (say June 2016 or later)
    if not validity.is_valid:
        module.report_configs = validity.valid_report_configs

    filter_choices = [
        {'slug': f.doc_type, 'description': f.short_description} for f in get_all_mobile_filter_configs()
    ]
    auto_filter_choices = [
        {'slug': f.slug, 'description': f.short_description} for f in get_auto_filter_configurations()

    ]
    from corehq.apps.app_manager.suite_xml.features.mobile_ucr import get_column_xpath_client_template, get_data_path
    data_path_placeholders = {}
    for r in module.report_configs:
        data_path_placeholders[r.report_id] = {}
        for chart_id in r.complete_graph_configs.keys():
            data_path_placeholders[r.report_id][chart_id] = get_data_path(r, app.domain)

    context = {
        'report_module_options': {
            'moduleName': module.name,
            'moduleFilter': module.module_filter,
            'availableReports': [_report_to_config(r) for r in all_reports],  # structure for all reports
            'currentReports': [r.to_json() for r in module.report_configs],  # config data for app reports
            'columnXpathTemplate': get_column_xpath_client_template(app.mobile_ucr_restore_version),
            'dataPathPlaceholders': data_path_placeholders,
            'languages': app.langs,
            'mobileUcrV1': app.mobile_ucr_restore_version == MOBILE_UCR_VERSION_1,
            'globalSyncDelay': Domain.get_by_name(app.domain).default_mobile_ucr_sync_interval,
        },
        'static_data_options': {
            'filterChoices': filter_choices,
            'autoFilterChoices': auto_filter_choices,
            'dateRangeOptions': [choice._asdict() for choice in get_simple_dateranges()],
        },
        'uuids_by_instance_id': get_uuids_by_instance_id(app.domain),
    }
    return context


def _get_fixture_columns_by_type(domain):
    return {
        fixture.tag: [field.field_name for field in fixture.fields]
        for fixture in FixtureDataType.by_domain(domain)
    }


def _setup_case_property_builder(app):
    defaults = ('name', 'date-opened', 'status', 'last_modified')
    if app.case_sharing:
        defaults += ('#owner_name',)
    return ParentCasePropertyBuilder.for_app(app, defaults=defaults)


# Parent case selection in case list: get modules whose case type is the parent of the given module's case type
def _get_modules_with_parent_case_type(app, module, case_property_builder, case_type_):
        parent_types = case_property_builder.get_parent_types(case_type_)
        modules = app.modules
        parent_module_ids = [mod.unique_id for mod in modules
                             if mod.case_type in parent_types]
        return [{
            'unique_id': mod.unique_id,
            'name': mod.name,
            'is_parent': mod.unique_id in parent_module_ids,
        } for mod in app.modules if mod.case_type != case_type_ and mod.unique_id != module.unique_id]


# Parent/child modules: get modules that may be used as parents of the given module
def _get_valid_parents_for_child_module(app, module):
    # If this module already has a child, it can't also have a parent
    for m in app.modules:
        if module.unique_id == getattr(m, 'root_module_id', None):
            return []

    # Modules that already have a parent may not themselves be parents
    invalid_ids = [m.unique_id for m in app.modules if getattr(m, 'root_module_id', None)]
    current_parent_id = getattr(module, 'root_module_id', None)
    if current_parent_id in invalid_ids:
        invalid_ids.remove(current_parent_id)

    # The current module is not allowed, but its parent is
    # Shadow modules are not allowed
    return [parent_module for parent_module in app.modules if (parent_module.unique_id not in invalid_ids)
            and not parent_module == module and parent_module.doc_type != "ShadowModule"
            and not parent_module.is_training_module]


def _case_list_form_options(app, module, case_type_, lang=None):
    options = OrderedDict()
    forms = [
        form
        for mod in app.get_modules() if module.unique_id != mod.unique_id
        for form in mod.get_forms() if form.is_registration_form(case_type_)
    ]
    langs = None if lang is None else [lang]
    options.update({f.unique_id: trans(f.name, langs) for f in forms})

    return {
        'options': options,
        'form': module.case_list_form,
    }


def _get_module_details_context(app, module, case_property_builder, case_type_):
    subcase_types = list(app.get_subcase_types(module.case_type))
    item = {
        'label': gettext_lazy('Case List'),
        'detail_label': gettext_lazy('Case Detail'),
        'type': 'case',
        'model': 'case',
        'subcase_types': subcase_types,
        'sort_elements': module.case_details.short.sort_elements,
        'short': module.case_details.short,
        'long': module.case_details.long,
    }
    case_properties = case_property_builder.get_properties(case_type_)
    if is_usercase_in_use(app.domain) and case_type_ != USERCASE_TYPE:
        usercase_properties = prefix_usercase_properties(case_property_builder.get_properties(USERCASE_TYPE))
        case_properties |= usercase_properties

    item['properties'] = sorted(case_properties)
    item['fixture_select'] = module.fixture_select

    if isinstance(module, AdvancedModule):
        details = [item]
        if app.commtrack_enabled:
            details.append({
                'label': gettext_lazy('Product List'),
                'detail_label': gettext_lazy('Product Detail'),
                'type': 'product',
                'model': 'product',
                'properties': ['name'],
                'sort_elements': module.product_details.short.sort_elements,
                'short': module.product_details.short,
                'subcase_types': subcase_types,
            })
    else:
        item['parent_select'] = module.parent_select
        details = [item]

    return details


def _case_list_form_not_allowed_reasons(module):
    reasons = []
    if module.put_in_root:
        reasons.append(_("'Menu Mode' is not configured as 'Display menu and then forms'"))
    if not module.all_forms_require_a_case():
        reasons.append(_("all forms in this case list must update a case, "
                         "which means that registration forms must go in a different case list"))
    if hasattr(module, 'parent_select'):
        app = module.get_app()
        if (not app.build_version or app.build_version < LooseVersion('2.23')) and module.parent_select.active:
            reasons.append(_("'Parent Selection' is configured"))
    return reasons


@no_conflict_require_POST
@require_can_edit_apps
@track_domain_request(calculated_prop='cp_n_saved_app_changes')
def edit_module_attr(request, domain, app_id, module_unique_id, attr):
    """
    Called to edit any (supported) module attribute, given by attr
    """
    attributes = {
        "all": None,
        "auto_select_case": None,
        "case_list": ('case_list-show', 'case_list-label'),
        "case_list-menu_item_media_audio": None,
        "case_list-menu_item_media_image": None,
        'case_list-menu_item_use_default_image_for_all': None,
        'case_list-menu_item_use_default_audio_for_all': None,
        "case_list_form_id": None,
        "case_list_form_label": None,
        "case_list_form_media_audio": None,
        "case_list_form_media_image": None,
        'case_list_form_use_default_image_for_all': None,
        'case_list_form_use_default_audio_for_all': None,
        "case_list_post_form_workflow": None,
        "case_type": None,
        'comment': None,
        "display_separately": None,
        "has_schedule": None,
        "media_audio": None,
        "media_image": None,
        "module_filter": None,
        "name": None,
        "name_enum": None,
        "parent_module": None,
        "put_in_root": None,
        "root_module_id": None,
        "source_module_id": None,
        "task_list": ('task_list-show', 'task_list-label'),
        "excl_form_ids": None,
        "display_style": None,
        "custom_icon_form": None,
        "custom_icon_text_body": None,
        "custom_icon_xpath": None,
        "use_default_image_for_all": None,
        "use_default_audio_for_all": None,
    }

    if attr not in attributes:
        return HttpResponseBadRequest()

    def should_edit(attribute):
        if attribute == attr:
            return True
        if 'all' == attr:
            if attributes[attribute]:
                for param in attributes[attribute]:
                    if not request.POST.get(param):
                        return False
                return True
            else:
                return request.POST.get(attribute) is not None

    app = get_app(domain, app_id)

    try:
        module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        # temporary fallback
        module = app.get_module(module_unique_id)

    lang = request.COOKIES.get('lang', app.langs[0])
    resp = {'update': {}, 'corrections': {}}
    if should_edit("custom_icon_form"):
        error_message = handle_custom_icon_edits(request, module, lang)
        if error_message:
            return json_response(
                {'message': error_message},
                status_code=400
            )

    if should_edit("name_enum"):
        name_enum = json.loads(request.POST.get("name_enum"))
        module.name_enum = [MappingItem(i) for i in name_enum]

    if should_edit("case_type"):
        case_type = request.POST.get("case_type", None)
        if case_type == USERCASE_TYPE and not isinstance(module, AdvancedModule):
            return HttpResponseBadRequest('"{}" is a reserved case type'.format(USERCASE_TYPE))
        elif case_type and not is_valid_case_type(case_type, module):
            return HttpResponseBadRequest("case type is improperly formatted")
        else:
            old_case_type = module["case_type"]
            module["case_type"] = case_type

            # rename other reference to the old case type
            all_advanced_modules = []
            modules_with_old_case_type_exist = False
            for mod in app.modules:
                if isinstance(mod, AdvancedModule):
                    all_advanced_modules.append(mod)

                modules_with_old_case_type_exist |= mod.case_type == old_case_type
            for mod in all_advanced_modules:
                for form in mod.forms:
                    for action in form.actions.get_load_update_actions():
                        if action.case_type == old_case_type and action.details_module == module_unique_id:
                            action.case_type = case_type

                    if mod.unique_id == module_unique_id or not modules_with_old_case_type_exist:
                        for action in form.actions.get_open_actions():
                            if action.case_type == old_case_type:
                                action.case_type = case_type

    if should_edit("put_in_root"):
        module["put_in_root"] = json.loads(request.POST.get("put_in_root"))
    if should_edit("display_style"):
        module["display_style"] = request.POST.get("display_style")
    if should_edit("source_module_id"):
        module["source_module_id"] = request.POST.get("source_module_id")
    if should_edit("display_separately"):
        module["display_separately"] = json.loads(request.POST.get("display_separately"))
    if should_edit("parent_module"):
        parent_module = request.POST.get("parent_module")
        module.parent_select.module_id = parent_module
        if module_case_hierarchy_has_circular_reference(module):
            return HttpResponseBadRequest(_("The case hierarchy contains a circular reference."))
    if should_edit("auto_select_case"):
        module["auto_select_case"] = request.POST.get("auto_select_case") == 'true'

    if app.enable_module_filtering and should_edit('module_filter'):
        module['module_filter'] = request.POST.get('module_filter')

    if should_edit('case_list_form_id'):
        module.case_list_form.form_id = request.POST.get('case_list_form_id')
    if should_edit('case_list_form_label'):
        module.case_list_form.label[lang] = request.POST.get('case_list_form_label')
    if should_edit('case_list_post_form_workflow'):
        module.case_list_form.post_form_workflow = request.POST.get('case_list_post_form_workflow')

    if should_edit("name"):
        name = request.POST.get("name", None)
        module["name"][lang] = name
        resp['update'] = {'.variable-module_name': trans(module.name, [lang], use_delim=False)}
    if should_edit('comment'):
        module.comment = request.POST.get('comment')
    for SLUG in ('case_list', 'task_list'):
        show = '{SLUG}-show'.format(SLUG=SLUG)
        label = '{SLUG}-label'.format(SLUG=SLUG)
        if request.POST.get(show) == 'true' and (request.POST.get(label) == ''):
            # Show item, but empty label, was just getting ignored
            return HttpResponseBadRequest("A label is required for {SLUG}".format(SLUG=SLUG))
        if should_edit(SLUG):
            module[SLUG].show = json.loads(request.POST[show])
            module[SLUG].label[lang] = request.POST[label]

    if should_edit("root_module_id"):
        old_root = module['root_module_id']
        if not request.POST.get("root_module_id"):
            module["root_module_id"] = None
        else:
            module["root_module_id"] = request.POST.get("root_module_id")
        if not old_root and module['root_module_id']:
            track_workflow(request.couch_user.username, "User associated module with a parent")
        elif old_root and not module['root_module_id']:
            track_workflow(request.couch_user.username, "User orphaned a child module")

    if should_edit('excl_form_ids') and isinstance(module, ShadowModule):
        excl = request.POST.getlist('excl_form_ids')
        excl.remove('0')  # Placeholder value to make sure excl_form_ids is POSTed when no forms are excluded
        module.excluded_form_ids = excl

    handle_media_edits(request, module, should_edit, resp, lang)
    handle_media_edits(request, module.case_list_form, should_edit, resp, lang, prefix='case_list_form_')
    handle_media_edits(request, module.case_list, should_edit, resp, lang, prefix='case_list-menu_item_')


    app.save(resp)
    resp['case_list-show'] = module.requires_case_details()
    return HttpResponse(json.dumps(resp))


def _new_advanced_module(request, domain, app, name, lang):
    module = app.add_module(AdvancedModule.new_module(name, lang))
    _init_module_case_type(module)
    module_id = module.id
    app.new_form(module_id, _("Untitled Form"), lang)

    app.save()
    response = back_to_main(request, domain, app_id=app.id, module_id=module_id)
    response.set_cookie('suppress_build_errors', 'yes')
    messages.info(request, _('Caution: Advanced modules are a labs feature'))
    return response


def _new_report_module(request, domain, app, name, lang):
    module = app.add_module(ReportModule.new_module(name, lang))
    # by default add all reports
    module.report_configs = [
        ReportAppConfig(
            report_id=report._id,
            header={lang: report.title},
            description={lang: report.description} if report.description else None,
        )
        for report in ReportConfiguration.by_domain(domain)
    ]
    app.save()
    return back_to_main(request, domain, app_id=app.id, module_id=module.id)


def _new_shadow_module(request, domain, app, name, lang):
    module = app.add_module(ShadowModule.new_module(name, lang))
    app.save()
    return back_to_main(request, domain, app_id=app.id, module_id=module.id)


def _new_training_module(request, domain, app, name, lang):
    name = name or 'Training'
    module = app.add_module(Module.new_training_module(name, lang))
    app.save()
    return back_to_main(request, domain, app_id=app.id, module_id=module.id)


@no_conflict_require_POST
@require_can_edit_apps
def delete_module(request, domain, app_id, module_unique_id):
    "Deletes a module from an app"
    app = get_app(domain, app_id)
    try:
        module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        return bail(request, domain, app_id)
    if module.get_child_modules():
        messages.error(request, _('"{}" has child menus. You must remove these before '
                                  'you can delete it.').format(module.default_name()))
        return back_to_main(request, domain, app_id)

    record = app.delete_module(module_unique_id)
    messages.success(
        request,
        _('You have deleted "{name}". <a href="{url}" class="post-link">Undo</a>').format(
            name=record.module.default_name(app=app),
            url=reverse('undo_delete_module', args=[domain, record.get_id])
        ),
        extra_tags='html'
    )
    app.save()
    clear_xmlns_app_id_cache(domain)
    return back_to_main(request, domain, app_id=app_id)


@no_conflict_require_POST
@require_can_edit_apps
def undo_delete_module(request, domain, record_id):
    record = DeleteModuleRecord.get(record_id)
    record.undo()
    messages.success(request, 'Module successfully restored.')
    return back_to_main(request, domain, app_id=record.app_id, module_id=record.module_id)


@no_conflict_require_POST
@require_can_edit_apps
def overwrite_module_case_list(request, domain, app_id, module_unique_id):
    app = get_app(domain, app_id)
    source_module_unique_id = request.POST['source_module_unique_id']
    source_module = app.get_module_by_unique_id(source_module_unique_id)
    dest_module = app.get_module_by_unique_id(module_unique_id)
    detail_type = request.POST['detail_type']
    assert detail_type in ['short', 'long']
    if not hasattr(source_module, 'case_details'):
        messages.error(
            request,
            _("Sorry, couldn't find case list configuration for module {}. "
              "Please report an issue if you believe this is a mistake.").format(source_module.default_name()))
    elif source_module.case_type != dest_module.case_type:
        messages.error(
            request,
            _("Please choose a module with the same case type as the current one ({}).").format(
                dest_module.case_type)
        )
    else:
        setattr(dest_module.case_details, detail_type, getattr(source_module.case_details, detail_type))
        app.save()
        messages.success(request, _('Case list updated form module {}.').format(source_module.default_name()))
    return back_to_main(request, domain, app_id=app_id, module_unique_id=module_unique_id)


def _update_search_properties(module, search_properties, lang='en'):
    """
    Updates the translation of a module's current search properties, and drops missing search properties.

    Labels in incoming search_properties aren't keyed by language, so lang specifies that.

    e.g.:

    >>> module = Module()
    >>> module.search_config.properties = [
    ...     CaseSearchProperty(name='name', label={'fr': 'Nom'}),
    ...     CaseSearchProperty(name='age', label={'fr': 'Âge'}),
    ... ]
    >>> search_properties = [
    ...     {'name': 'name', 'label': 'Name'},
    ...     {'name': 'dob'. 'label': 'Date of birth'}
    ... ]  # Incoming search properties' labels are not dictionaries
    >>> lang = 'en'
    >>> list(_update_search_properties(module, search_properties, lang)) == [
    ...     {'name': 'name', 'label': {'fr': 'Nom', 'en': 'Name'}},
    ...     {'name': 'dob'. 'label': {'en': 'Date of birth'}},
    ... ]  # English label is added, "age" property is dropped
    True

    """
    current = {p.name: p.label for p in module.search_config.properties}
    for prop in search_properties:
        if prop['name'] in current:
            label = current[prop['name']].copy()
            label.update({lang: prop['label']})
        else:
            label = {lang: prop['label']}
        yield {
            'name': prop['name'],
            'label': label
        }


@no_conflict_require_POST
@require_can_edit_apps
def edit_module_detail_screens(request, domain, app_id, module_unique_id):
    """
    Overwrite module case details. Only overwrites components that have been
    provided in the request. Components are short, long, filter, parent_select,
    fixture_select and sort_elements.
    """
    params = json_request(request.POST)
    detail_type = params.get('type')
    short = params.get('short', None)
    long_ = params.get('long', None)
    tabs = params.get('tabs', None)
    filter = params.get('filter', ())
    custom_xml = params.get('custom_xml', None)
    parent_select = params.get('parent_select', None)
    fixture_select = params.get('fixture_select', None)
    sort_elements = params.get('sort_elements', None)
    persist_case_context = params.get('persistCaseContext', None)
    persistent_case_context_xml = params.get('persistentCaseContextXML', None)
    use_case_tiles = params.get('useCaseTiles', None)
    persist_tile_on_forms = params.get("persistTileOnForms", None)
    persistent_case_tile_from_module = params.get("persistentCaseTileFromModule", None)
    pull_down_tile = params.get("enableTilePullDown", None)
    sort_nodeset_columns = params.get("sortNodesetColumns", None)
    print_template = params.get('printTemplate', None)
    case_list_lookup = params.get("case_list_lookup", None)
    search_properties = params.get("search_properties")
    custom_variables = {
        'short': params.get("short_custom_variables", None),
        'long': params.get("long_custom_variables", None)
    }

    app = get_app(domain, app_id)

    try:
        module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        # temporary fallback
        module = app.get_module(module_unique_id)

    if detail_type == 'case':
        detail = module.case_details
    else:
        try:
            detail = getattr(module, '{0}_details'.format(detail_type))
        except AttributeError:
            return HttpResponseBadRequest("Unknown detail type '%s'" % detail_type)

    lang = request.COOKIES.get('lang', app.langs[0])
    if short is not None:
        detail.short.columns = list(map(DetailColumn.from_json, short))
        if persist_case_context is not None:
            detail.short.persist_case_context = persist_case_context
            detail.short.persistent_case_context_xml = persistent_case_context_xml
        if use_case_tiles is not None:
            detail.short.use_case_tiles = use_case_tiles
        if persist_tile_on_forms is not None:
            detail.short.persist_tile_on_forms = persist_tile_on_forms
        if persistent_case_tile_from_module is not None:
            detail.short.persistent_case_tile_from_module = persistent_case_tile_from_module
        if pull_down_tile is not None:
            detail.short.pull_down_tile = pull_down_tile
        if case_list_lookup is not None:
            _save_case_list_lookup_params(detail.short, case_list_lookup, lang)

    if long_ is not None:
        detail.long.columns = list(map(DetailColumn.from_json, long_))
        if tabs is not None:
            detail.long.tabs = list(map(DetailTab.wrap, tabs))
        if print_template is not None:
            detail.long.print_template = print_template
    if filter != ():
        # Note that we use the empty tuple as the sentinel because a filter
        # value of None represents clearing the filter.
        detail.short.filter = filter
    if custom_xml is not None:
        detail.short.custom_xml = custom_xml

    if custom_variables['short'] is not None:
        try:
            etree.fromstring("<variables>{}</variables>".format(custom_variables['short']))
        except etree.XMLSyntaxError as error:
            return HttpResponseBadRequest(
                "There was an issue with your custom variables: {}".format(error.message)
            )
        detail.short.custom_variables = custom_variables['short']

    if custom_variables['long'] is not None:
        try:
            etree.fromstring("<variables>{}</variables>".format(custom_variables['long']))
        except etree.XMLSyntaxError as error:
            return HttpResponseBadRequest(
                "There was an issue with your custom variables: {}".format(error.message)
            )
        detail.long.custom_variables = custom_variables['long']

    if sort_nodeset_columns is not None:
        detail.long.sort_nodeset_columns = sort_nodeset_columns

    if sort_elements is not None:
        # Attempt to map new elements to old so we don't lose translations
        # Imperfect because the same field may be used multiple times, or user may change field
        old_elements_by_field = {e['field']: e for e in detail.short.sort_elements}

        detail.short.sort_elements = []
        for sort_element in sort_elements:
            item = SortElement()
            item.field = sort_element['field']
            item.type = sort_element['type']
            item.direction = sort_element['direction']
            item.blanks = sort_element['blanks']
            if item.field in old_elements_by_field:
                item.display = old_elements_by_field[item.field].display
            item.display[lang] = sort_element['display']
            if toggles.SORT_CALCULATION_IN_CASE_LIST.enabled(domain):
                item.sort_calculation = sort_element['sort_calculation']
            else:
                item.sort_calculation = ""
            detail.short.sort_elements.append(item)
    if parent_select is not None:
        module.parent_select = ParentSelect.wrap(parent_select)
        if module_case_hierarchy_has_circular_reference(module):
            return HttpResponseBadRequest(_("The case hierarchy contains a circular reference."))
    if fixture_select is not None:
        module.fixture_select = FixtureSelect.wrap(fixture_select)
    if search_properties is not None:
        if (
                search_properties.get('properties') is not None
                or search_properties.get('default_properties') is not None
        ):
            module.search_config = CaseSearch(
                properties=[
                    CaseSearchProperty.wrap(p)
                    for p in _update_search_properties(
                        module,
                        search_properties.get('properties'), lang
                    )
                ],
                relevant=(
                    search_properties.get('relevant')
                    if search_properties.get('relevant') is not None
                    else CLAIM_DEFAULT_RELEVANT_CONDITION
                ),
                include_closed=bool(search_properties.get('include_closed')),
                search_button_display_condition=search_properties.get('search_button_display_condition', ""),
                blacklisted_owner_ids_expression=search_properties.get('blacklisted_owner_ids_expression', ""),
                default_properties=[
                    DefaultCaseSearchProperty.wrap(p)
                    for p in search_properties.get('default_properties')
                ]
            )

    resp = {}
    app.save(resp)
    return json_response(resp)


@no_conflict_require_POST
@require_can_edit_apps
def edit_report_module(request, domain, app_id, module_unique_id):
    """
    Overwrite module case details. Only overwrites components that have been
    provided in the request. Components are short, long, filter, parent_select,
    and sort_elements.
    """
    params = json_request(request.POST)
    app = get_app(domain, app_id)

    try:
        module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        # temporary fallback
        module = app.get_module(module_unique_id)

    assert isinstance(module, ReportModule)
    module.name = params['name']

    try:
        module.report_configs = [ReportAppConfig.wrap(spec) for spec in params['reports']]
    except Exception:
        notify_exception(
            request,
            message="Something went wrong while editing report modules",
            details={'domain': domain, 'app_id': app_id, }
        )
        return HttpResponseBadRequest(_("There was a problem processing your request."))

    if app.enable_module_filtering:
        module['module_filter'] = request.POST.get('module_filter')

    module.media_image.update(params['multimedia']['mediaImage'])
    module.media_audio.update(params['multimedia']['mediaAudio'])

    if 'name_enum' in params:
        name_enum = json.loads(request.POST.get("name_enum"))
        module.name_enum = [MappingItem(i) for i in name_enum]

    try:
        app.save()
    except Exception:
        notify_exception(
            request,
            message="Something went wrong while saving app {} while editing report modules".format(app_id),
            details={'domain': domain, 'app_id': app_id, }
        )
        return HttpResponseBadRequest(_("There was a problem processing your request."))

    get_uuids_by_instance_id.clear(domain)
    return json_response('success')


def validate_module_for_build(request, domain, app_id, module_unique_id, ajax=True):
    app = get_app(domain, app_id)
    try:
        module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        try:
            # temporary fallback
            module = app.get_module(module_unique_id)
        except ModuleNotFoundException:
            raise Http404()

    errors = module.validate_for_build()
    lang, langs = get_langs(request, app)

    response_html = render_to_string("app_manager/partials/build_errors.html", {
        'request': request,
        'app': app,
        'build_errors': errors,
        'not_actual_build': True,
        'domain': domain,
        'langs': langs,
        'lang': lang,
    })
    if ajax:
        return json_response({'error_html': response_html})
    return HttpResponse(response_html)


@no_conflict_require_POST
@require_can_edit_apps
def new_module(request, domain, app_id):
    "Adds a module to an app"
    app = get_app(domain, app_id)
    from corehq.apps.app_manager.views.utils import get_default_followup_form_xml
    lang = request.COOKIES.get('lang', app.langs[0])
    name = request.POST.get('name')
    module_type = request.POST.get('module_type', 'case')

    if module_type == 'biometrics':
        enroll_module, enroll_form_id = _init_biometrics_enroll_module(app, lang)
        _init_biometrics_identify_module(app, lang, enroll_form_id)

        app.save()

        response = back_to_main(request, domain, app_id=app_id,
                                module_id=enroll_module.id, form_id=0)
        response.set_cookie('suppress_build_errors', 'yes')
        return response
    elif module_type == 'case' or module_type == 'survey':  # survey option added for V2
        if module_type == 'case':
            name = name or 'Case List'
        else:
            name = name or 'Surveys'

        module = app.add_module(Module.new_module(name, lang))
        module_id = module.id

        form_id = None
        unstructured = add_ons.show("empty_case_lists", request, app)
        if module_type == 'case':
            if not unstructured:
                form_id = 0

                # registration form
                register = app.new_form(module_id, _("Registration Form"), lang)
                register.actions.open_case = OpenCaseAction(condition=FormActionCondition(type='always'))
                register.actions.update_case = UpdateCaseAction(
                    condition=FormActionCondition(type='always'))

                # one followup form
                msg = _("This is your follow up form. "
                        "Delete this label and add questions for any follow up visits.")
                attachment = get_default_followup_form_xml(context={'lang': lang, 'default_label': msg})
                followup = app.new_form(module_id, _("Followup Form"), lang, attachment=attachment)
                followup.requires = "case"
                followup.actions.update_case = UpdateCaseAction(condition=FormActionCondition(type='always'))

            _init_module_case_type(module)
        else:
            form_id = 0
            app.new_form(module_id, _("Survey"), lang)

        app.save()
        response = back_to_main(request, domain, app_id=app_id,
                                module_id=module_id, form_id=form_id)
        response.set_cookie('suppress_build_errors', 'yes')
        return response
    elif module_type in MODULE_TYPE_MAP:
        fn = MODULE_TYPE_MAP[module_type][FN]
        validations = MODULE_TYPE_MAP[module_type][VALIDATIONS]
        error = next((v[1] for v in validations if v[0](app)), None)
        if error:
            messages.warning(request, error)
            return back_to_main(request, domain, app_id=app.id)
        else:
            return fn(request, domain, app, name, lang)
    else:
        logger.error('Unexpected module type for new module: "%s"' % module_type)
        return back_to_main(request, domain, app_id=app_id)


# Set initial module case type, copying from another module in the same app
def _init_module_case_type(module):
    app = module.get_app()
    app_case_types = [m.case_type for m in app.modules if m.case_type]
    if len(app_case_types):
        module.case_type = app_case_types[0]
    else:
        module.case_type = 'case'


def _init_biometrics_enroll_module(app, lang):
    """
    Creates Enrolment Module for Biometrics
    """
    module = app.add_module(Module.new_module(_("Registration"), lang))

    form_name = _("Enroll New Person")

    context = {
        'xmlns_uuid': str(uuid.uuid4()).upper(),
        'form_name': form_name,
        'name_label': _("What is your name?"),
        'simprints_enrol_label': _("Scan Fingerprints"),
        'lang': lang,
    }
    context.update(app.biometric_context)
    attachment = render_to_string(
        "app_manager/simprints_enrolment_form.xml",
        context=context
    )

    enroll = app.new_form(module.id, form_name, lang, attachment=attachment)
    enroll.actions.open_case = OpenCaseAction(
        name_path="/data/name",
        condition=FormActionCondition(type='always'),
    )
    enroll.actions.update_case = UpdateCaseAction(
        update={
            'simprintsId': '/data/simprintsId',
            'rightIndex': '/data/rightIndex',
            'rightThumb': '/data/rightThumb',
            'leftIndex': '/data/leftIndex',
            'leftThumb': '/data/leftThumb',
        },
        condition=FormActionCondition(type='always'),
    )

    module.case_type = 'person'

    return module, enroll.get_unique_id()


def _init_biometrics_identify_module(app, lang, enroll_form_id):
    """
    Creates Identification Module for Biometrics
    """
    module = app.add_module(Module.new_module(_("Identify Registered Person"), lang))

    # make sure app has Register From Case List Add-On enabled
    app.add_ons["register_from_case_list"] = True

    # turn on Register from Case List with Simprints Enrolment form
    module.case_list_form = CaseListForm(
        form_id=enroll_form_id,
        label=dict([(lang, _("Enroll New Person"))]),
    )
    case_list = module.case_details.short
    case_list.lookup_enabled = True
    case_list.lookup_action = "com.simprints.id.IDENTIFY"
    case_list.lookup_name = _("Scan Fingerprint")
    case_list.lookup_extras = list([
        dict(key=key, value="'{}'".format(value))
        for key, value in app.biometric_context.items()
    ])
    case_list.lookup_responses = [
        {'key': 'fake'},
    ]
    case_list.lookup_display_results = True
    case_list.lookup_field_header[lang] = _("Confidence")
    case_list.lookup_field_template = 'simprintsId'

    form_name = _("Followup with Person")

    context = {
        'xmlns_uuid': str(uuid.uuid4()).upper(),
        'form_name': form_name,
        'lang': lang,
        'placeholder_label': mark_safe(_(
            "This is your follow up form for {}. Delete this label and add "
            "questions for any follow up visits."
        ).format(
            "<output value=\"instance('casedb')/casedb/case[@case_id = "
            "instance('commcaresession')/session/data/case_id]/case_name\" "
            "vellum:value=\"#case/case_name\" />"
        ))
    }
    attachment = render_to_string(
        "app_manager/simprints_followup_form.xml",
        context=context
    )

    identify = app.new_form(module.id, form_name, lang, attachment=attachment)
    identify.requires = 'case'
    identify.actions.update_case = UpdateCaseAction(
        condition=FormActionCondition(type='always'))

    module.case_type = 'person'


def _save_case_list_lookup_params(short, case_list_lookup, lang):
    short.lookup_enabled = case_list_lookup.get("lookup_enabled", short.lookup_enabled)
    short.lookup_autolaunch = case_list_lookup.get("lookup_autolaunch", short.lookup_autolaunch)
    short.lookup_action = case_list_lookup.get("lookup_action", short.lookup_action)
    short.lookup_name = case_list_lookup.get("lookup_name", short.lookup_name)
    short.lookup_extras = case_list_lookup.get("lookup_extras", short.lookup_extras)
    short.lookup_responses = case_list_lookup.get("lookup_responses", short.lookup_responses)
    short.lookup_image = case_list_lookup.get("lookup_image", short.lookup_image)
    short.lookup_display_results = case_list_lookup.get("lookup_display_results", short.lookup_display_results)
    if "lookup_field_header" in case_list_lookup:
        short.lookup_field_header[lang] = case_list_lookup["lookup_field_header"]
    short.lookup_field_template = case_list_lookup.get("lookup_field_template", short.lookup_field_template)


@require_GET
@require_deploy_apps
def view_module(request, domain, app_id, module_unique_id):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, module_unique_id=module_unique_id)


@require_GET
@require_deploy_apps
def view_module_legacy(request, domain, app_id, module_id):
    """
    This view has been kept around to not break any documentation on example apps
    and partner-distributed documentation on existing apps.
    PLEASE DO NOT DELETE.
    """
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, module_id)


class ExistingCaseTypesView(LoginAndDomainMixin, View):
    urlname = 'existing_case_types'

    def get(self, request, domain):
        return JsonResponse({
            'existing_case_types': list(get_case_types_for_domain_es(domain))
        })


FN = 'fn'
VALIDATIONS = 'validations'
MODULE_TYPE_MAP = {
    'advanced': {
        FN: _new_advanced_module,
        VALIDATIONS: []
    },
    'report': {
        FN: _new_report_module,
        VALIDATIONS: []
    },
    'shadow': {
        FN: _new_shadow_module,
        VALIDATIONS: []
    },
    'training': {
        FN: _new_training_module,
        VALIDATIONS: []
    },
}
