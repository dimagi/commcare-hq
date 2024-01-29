import json
import logging
import re
from dataclasses import asdict
from collections import OrderedDict
from functools import partial

from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views import View
from django.views.decorators.http import require_GET
from django_prbac.utils import has_privilege
from looseversion import LooseVersion

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager import add_ons
from corehq.apps.app_manager.app_schemas.case_properties import (
    ParentCasePropertyBuilder,
)
from corehq.apps.app_manager.const import (
    CASE_LIST_FILTER_LOCATIONS_FIXTURE,
    MOBILE_UCR_VERSION_1,
    REGISTRY_WORKFLOW_LOAD_CASE,
    REGISTRY_WORKFLOW_SMART_LINK,
    USERCASE_TYPE,
    MULTI_SELECT_MAX_SELECT_VALUE,
)
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import (
    no_conflict_require_POST,
    require_can_edit_apps,
    require_deploy_apps,
)
from corehq.apps.app_manager.exceptions import (
    AppMisconfigurationError,
    CaseSearchConfigError,
)
from corehq.apps.app_manager.models import (
    Application,
    AdvancedModule,
    CaseListForm,
    CaseSearch,
    CaseSearchCustomSortProperty,
    CaseSearchProperty,
    DefaultCaseSearchProperty,
    DeleteModuleRecord,
    Detail,
    DetailColumn,
    DetailTab,
    FixtureSelect,
    FormActionCondition,
    Module,
    ModuleNotFoundException,
    OpenCaseAction,
    ParentSelect,
    ReportAppConfig,
    ReportModule,
    ShadowModule,
    SortElement,
    UpdateCaseAction,
    get_all_mobile_filter_configs,
    get_auto_filter_configurations, ConditionalCaseUpdate, CaseTileGroupConfig,
)
from corehq.apps.app_manager.suite_xml.features.case_tiles import case_tile_template_config, CaseTileTemplates
from corehq.apps.app_manager.suite_xml.features.mobile_ucr import (
    get_uuids_by_instance_id,
)
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans, trans
from corehq.apps.app_manager.util import (
    generate_xmlns,
    is_usercase_in_use,
    is_valid_case_type,
    module_case_hierarchy_has_circular_reference,
    module_offers_search,
    prefix_usercase_properties,
)
from corehq.apps.app_manager.views.media_utils import (
    handle_media_edits,
)
from corehq.apps.app_manager.views.utils import (
    back_to_main,
    bail,
    capture_user_errors,
    clear_xmlns_app_id_cache,
    get_langs,
    validate_custom_assertions,
    handle_custom_icon_edits,
    handle_shadow_child_modules,
    set_session_endpoint,
    set_case_list_session_endpoint,
    set_shadow_module_and_form_session_endpoint
)
from corehq.apps.app_manager.xform import CaseError
from corehq.apps.app_manager.xpath_validator import validate_xpath
from corehq.apps.case_search.models import case_search_enabled_for_domain
from corehq.apps.domain.decorators import (
    LoginAndDomainMixin,
    track_domain_request,
)
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.fixturegenerators import item_lists_by_app, REPORT_FIXTURE, LOOKUP_TABLE_FIXTURE
from corehq.apps.fixtures.models import LookupTable
from corehq.apps.hqmedia.controller import MultimediaHTMLUploadController
from corehq.apps.hqmedia.models import (
    ApplicationMediaReference,
    CommCareMultimedia,
)
from corehq.apps.hqmedia.views import ProcessDetailPrintTemplateUploadView
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.registry.utils import get_data_registry_dropdown_options
from corehq.apps.reports.analytics.esaccessors import (
    get_case_types_for_domain_es
)
from corehq.apps.data_dictionary.util import get_data_dict_deprecated_case_types
from corehq.apps.reports.daterange import get_simple_dateranges
from corehq.apps.userreports.dbaccessors import get_report_and_registry_report_configs_for_domain
from corehq.apps.userreports.models import (
    StaticReportConfiguration,
)
from corehq.toggles import toggles_enabled_for_request
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_request, json_response

logger = logging.getLogger(__name__)


def get_module_template(user, module):
    if isinstance(module, AdvancedModule):
        return "app_manager/module_view_advanced.html"
    elif isinstance(module, ReportModule):
        return "app_manager/module_view_report.html"
    else:
        return "app_manager/module_view.html"


def get_module_view_context(request, app, module, lang=None):
    context = {
        'edit_name_url': reverse('edit_module_attr', args=[app.domain, app.id, module.unique_id, 'name']),
        'show_search_workflow': (
            app.cloudcare_enabled
            and has_privilege(request, privileges.CLOUDCARE)
            and toggles.USH_CASE_CLAIM_UPDATES.enabled(app.domain)
        ),
        'custom_assertions': [
            {'test': assertion.test, 'text': assertion.text.get(lang)}
            for assertion in module.custom_assertions
        ],
    }
    module_brief = {
        'id': module.id,
        'case_type': module.case_type,
        'lang': lang,
        'langs': app.langs,
        'module_type': module.module_type,
        'requires_case_details': module.requires_case_details(),
        'unique_id': module.unique_id,
    }
    case_property_builder = _setup_case_property_builder(app)
    show_advanced_settings = (
        not module.is_surveys
        or add_ons.show("register_from_case_list", request, app, module)
        or add_ons.show("case_list_menu_item", request, app, module) and not isinstance(module, ShadowModule)
        or toggles.CUSTOM_ASSERTIONS.enabled(app.domain)
    )
    if toggles.MOBILE_UCR.enabled(app.domain):
        show_advanced_settings = True
        module_brief.update({
            'report_context_tile': module.report_context_tile,
        })
    if isinstance(module, AdvancedModule):
        show_advanced_settings = True
        module_brief.update({
            'auto_select_case': module.auto_select_case,
            'has_schedule': module.has_schedule,
        })
        context.update(_get_shared_module_view_context(request, app, module, case_property_builder, lang))
        context.update(_get_advanced_module_view_context(app, module))
    elif isinstance(module, ReportModule):
        context.update(_get_report_module_context(app, module))
    else:
        context.update(_get_shared_module_view_context(request, app, module, case_property_builder, lang))
        context.update(_get_basic_module_view_context(request, app, module, case_property_builder))
    if isinstance(module, ShadowModule):
        context.update(_get_shadow_module_view_context(app, module, lang))

    context['show_advanced_settings'] = show_advanced_settings
    context['module_brief'] = module_brief
    return context


def _get_shared_module_view_context(request, app, module, case_property_builder, lang=None):
    '''
    Get context items that are used by both basic and advanced modules.
    '''
    item_lists = item_lists_by_app(app, module) if app.enable_search_prompt_appearance else []
    case_types = set(module.search_config.additional_case_types) | {module.case_type}
    case_list_map_enabled = toggles.CASE_LIST_MAP.enabled(app.domain)
    case_tile_template_option_to_configs = [
        (template, asdict(case_tile_template_config(template[0]))) for template in CaseTileTemplates.choices
    ]
    case_tile_template_option_to_configs_filtered = [
        option_to_config for option_to_config in case_tile_template_option_to_configs
        if case_list_map_enabled or not option_to_config[1]['has_map']
    ]

    fixture_column_options = _get_fixture_columns_options(app.domain)

    context = {
        'details': _get_module_details_context(request, app, module, case_property_builder),
        'case_list_form_options': _case_list_form_options(app, module, lang),
        'form_endpoint_options': _form_endpoint_options(app, module, lang),
        'valid_parents_for_child_module': _get_valid_parents_for_child_module(app, module),
        'shadow_parent': _get_shadow_parent(app, module),
        'case_types': {m.case_type for m in app.modules if m.case_type},
        'session_endpoints_enabled': toggles.SESSION_ENDPOINTS.enabled(app.domain),
        'data_registry_enabled': app.supports_data_registry,
        'data_registries': get_data_registry_dropdown_options(app.domain, required_case_types=case_types),
        'data_registry_workflow_choices': (
            (REGISTRY_WORKFLOW_LOAD_CASE, _("Load external case into form")),
            (REGISTRY_WORKFLOW_SMART_LINK, _("Smart link to external domain")),
        ),
        'js_options': {
            'fixture_columns_by_type': fixture_column_options,
            'is_search_enabled': case_search_enabled_for_domain(app.domain),
            'search_prompt_appearance_enabled': app.enable_search_prompt_appearance,
            'has_geocoder_privs': (
                domain_has_privilege(app.domain, privileges.GEOCODER)
                and toggles.USH_CASE_CLAIM_UPDATES.enabled(app.domain)
            ),
            'ush_case_claim_2_53': app.ush_case_claim_2_53,
            'item_lists': item_lists,
            'has_lookup_tables': bool([i for i in item_lists if i['fixture_type'] == LOOKUP_TABLE_FIXTURE]),
            'has_mobile_ucr': bool([i for i in item_lists if i['fixture_type'] == REPORT_FIXTURE]),
            'default_value_expression_enabled': app.enable_default_value_expression,
            'case_tile_template_options':
                [option_to_config[0] for option_to_config in case_tile_template_option_to_configs_filtered],
            'case_tile_template_configs': {option_to_config[0][0]: option_to_config[1]
                                           for option_to_config in case_tile_template_option_to_configs_filtered},
            'search_config': {
                'search_properties':
                    module.search_config.properties if module_offers_search(module) else [],
                'default_properties':
                    module.search_config.default_properties if module_offers_search(module) else [],
                'custom_sort_properties':
                    module.search_config.custom_sort_properties if module_offers_search(module) else [],
                'auto_launch': module.search_config.auto_launch if module_offers_search(module) else False,
                'default_search': module.search_config.default_search if module_offers_search(module) else False,
                'search_filter': module.search_config.search_filter if module_offers_search(module) else "",
                'search_button_display_condition':
                    module.search_config.search_button_display_condition if module_offers_search(module) else "",
                'additional_relevant':
                    module.search_config.additional_relevant if module_offers_search(module) else "",
                'blacklisted_owner_ids_expression': (
                    module.search_config.blacklisted_owner_ids_expression if module_offers_search(module) else ""),
                # populate labels even if module_offers_search is false - search_config might just not exist yet
                'search_label':
                    module.search_config.search_label.label if hasattr(module, 'search_config') else "",
                'search_again_label':
                    module.search_config.search_again_label.label if hasattr(module, 'search_config') else "",
                'title_label':
                    module.search_config.title_label if hasattr(module, 'search_config') else "",
                'description':
                    module.search_config.description if hasattr(module, 'search_config') else "",
                'data_registry': module.search_config.data_registry if module.search_config.data_registry else "",
                'data_registry_workflow': module.search_config.data_registry_workflow,
                'additional_registry_cases': module.search_config.additional_registry_cases,
                'custom_related_case_property': module.search_config.custom_related_case_property,
                'inline_search': module.search_config.inline_search,
                'instance_name': module.search_config.instance_name or "",
                'include_all_related_cases': module.search_config.include_all_related_cases,
                'dynamic_search': app.split_screen_dynamic_search,
                'search_on_clear': module.search_config.search_on_clear,
            },
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


def _get_basic_module_view_context(request, app, module, case_property_builder):
    return {
        'parent_case_modules': get_modules_with_parent_case_type(app, module, case_property_builder),
        'all_case_modules': get_all_case_modules(app, module),
        'case_list_form_not_allowed_reasons': _case_list_form_not_allowed_reasons(module),
        'child_module_enabled': (
            add_ons.show("submenus", request, app, module=module) and not module.is_training_module
        ),
    }


def _get_shadow_module_view_context(app, module, lang=None):
    langs = None if lang is None else [lang]

    def get_mod_dict(mod):
        return {
            'unique_id': mod.unique_id,
            'name': trans(mod.name, langs),
            'root_module_id': mod.root_module_id,
            'session_endpoint_id': mod.session_endpoint_id,
            'forms': [{
                'unique_id': f.unique_id,
                'name': trans(f.name, langs),
                'session_endpoint_id': f.session_endpoint_id
            } for f in mod.get_forms()]
        }

    return {
        'case_list_form_not_allowed_reasons': _case_list_form_not_allowed_reasons(module),
        'shadow_module_options': {
            'modules': [get_mod_dict(m) for m in app.modules if m.module_type in ['basic', 'advanced']],
            'source_module_id': module.source_module_id,
            'excluded_form_ids': module.excluded_form_ids,
            'form_session_endpoints': module.form_session_endpoints,
            'shadow_module_version': module.shadow_module_version,
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

    all_reports = get_report_and_registry_report_configs_for_domain(app.domain) + \
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
    from corehq.apps.app_manager.suite_xml.features.mobile_ucr import (
        get_column_xpath_client_template,
        get_data_path
    )
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
            'reportContextTile': module.report_context_tile,
        },
        'static_data_options': {
            'filterChoices': filter_choices,
            'autoFilterChoices': auto_filter_choices,
            'dateRangeOptions': [choice._asdict() for choice in get_simple_dateranges()],
        },
        'uuids_by_instance_id': get_uuids_by_instance_id(app),
    }
    return context


def _get_fixture_columns_options(domain):
    fixture_column_options = _get_fixture_columns_by_type(domain)
    fixture_column_options[CASE_LIST_FILTER_LOCATIONS_FIXTURE] = [
        '@id', 'name', 'site_code'
    ]
    return fixture_column_options


def _get_fixture_columns_by_type(domain):
    return {
        fixture.tag: [field.name for field in fixture.fields]
        for fixture in LookupTable.objects.by_domain(domain)
    }


def _setup_case_property_builder(app):
    defaults = ('name', 'date-opened', 'status', 'last_modified')
    if app.case_sharing:
        defaults += ('#owner_name',)
    return ParentCasePropertyBuilder.for_app(app, defaults=defaults)


# Parent case selection in case list: get modules whose case type is the parent of the given module's case type
def get_modules_with_parent_case_type(app, module, case_property_builder=None):
    if case_property_builder is None:
        case_property_builder = _setup_case_property_builder(app)

    parent_types = case_property_builder.get_parent_types(module.case_type)
    modules = app.modules
    parent_module_ids = [
        mod.unique_id for mod in modules
        if mod.case_type in parent_types
    ]

    return [{
        'unique_id': mod.unique_id,
        'name': mod.name,
        'is_parent': mod.unique_id in parent_module_ids
    } for mod in app.modules
        if mod.case_type != module.case_type
        and mod.unique_id != module.unique_id
        and not mod.is_multi_select()
    ]


def get_all_case_modules(app, module):
    # return all case modules except the given module
    return [{
        'unique_id': mod.unique_id,
        'name': mod.name,
        'is_parent': False,
    } for mod in app.get_modules() if mod.case_type and mod.unique_id != module.unique_id]


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
    # Shadow modules are not allowed to be selected as parents
    return [parent_module for parent_module in app.modules if (parent_module.unique_id not in invalid_ids)
            and not parent_module == module and parent_module.doc_type != "ShadowModule"
            and not parent_module.is_training_module]


def _get_shadow_parent(app, module):
    # If this module is a shadow module and has a parent, return it
    if module.module_type == 'shadow' and getattr(module, 'root_module_id', None):
        return app.get_module_by_unique_id(module.root_module_id)
    return None


def _case_list_form_options(app, module, lang=None):
    options = OrderedDict()
    reg_forms = [
        form
        for mod in app.get_modules() if module.unique_id != mod.unique_id
        for form in mod.get_forms() if form.is_registration_form(module.case_type)
    ]
    langs = None if lang is None else [lang]
    options.update({f.unique_id: {
        'name': trans(f.name, langs),
        'post_form_workflow': f.post_form_workflow,
        'is_registration_form': True,
    } for f in reg_forms})
    if (hasattr(module, 'parent_select')  # AdvancedModule doesn't have parent_select
            and toggles.FOLLOWUP_FORMS_AS_CASE_LIST_FORM
            and module.parent_select.active):
        followup_forms = get_parent_select_followup_forms(app, module)
        if followup_forms:
            options.update({f.unique_id: {
                'name': trans(f.name, langs),
                'post_form_workflow': f.post_form_workflow,
                'is_registration_form': False,
            } for f in followup_forms})
    return {
        'options': options,
        'form': module.case_list_form,
    }


def _form_endpoint_options(app, module, lang=None):
    langs = None if lang is None else [lang]
    forms = [
        {
            "id": form.session_endpoint_id,
            "form_name": trans(form.name, langs),
            "module_name": trans(mod.name, langs),
            "module_case_type": mod.case_type
        }
        for mod in app.get_modules()
        for form in mod.get_forms() if form.session_endpoint_id and form.is_auto_submitting_form(module.case_type)
    ]
    return forms


def get_parent_select_followup_forms(app, module):
    if not module.parent_select.active or not module.parent_select.module_id:
        return []
    parent_module = app.get_module_by_unique_id(
        module.parent_select.module_id,
        error=_("Case list used by Select Parent First in '{}' not found").format(
            module.default_name()),
    )
    parent_case_type = parent_module.case_type
    rel = module.parent_select.relationship
    if (rel == 'parent' and parent_case_type != module.case_type) or rel is None:
        return [
            form
            for mod in app.get_modules() if mod.case_type == parent_case_type
            for form in mod.get_forms() if form.requires_case() and not form.is_registration_form()
        ]
    else:
        return []


def _get_module_details_context(request, app, module, case_property_builder, messages=messages):
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
    try:
        case_properties = case_property_builder.get_properties(module.case_type)
        if is_usercase_in_use(app.domain) and module.case_type != USERCASE_TYPE:
            usercase_properties = prefix_usercase_properties(case_property_builder.get_properties(USERCASE_TYPE))
            case_properties |= usercase_properties
    except CaseError as e:
        case_properties = []
        messages.error(request, "Error in Case Management: %s" % e)

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
@capture_user_errors
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
        "case_list_form_expression": None,
        "case_list_form_media_audio": None,
        "case_list_form_media_image": None,
        'case_list_form_use_default_image_for_all': None,
        'case_list_form_use_default_audio_for_all': None,
        "case_list_post_form_workflow": None,
        "case_type": None,
        "additional_case_types": [],
        'comment': None,
        "display_separately": None,
        "has_schedule": None,
        "media_audio": None,
        "media_image": None,
        "module_filter": None,
        "name": None,
        "no_items_text": None,
        "parent_module": None,
        "put_in_root": None,
        "report_context_tile": None,
        "root_module_id": None,
        "source_module_id": None,
        "task_list": ('task_list-show', 'task_list-label'),
        "excl_form_ids": None,
        "form_session_endpoints": None,
        "display_style": None,
        "custom_icon_form": None,
        "custom_icon_text_body": None,
        "custom_icon_xpath": None,
        "use_default_image_for_all": None,
        "use_default_audio_for_all": None,
        "session_endpoint_id": None,
        "case_list_session_endpoint_id": None,
        'custom_assertions': None,
        'lazy_load_case_list_fields': None,
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
        handle_custom_icon_edits(request, module, lang)
    if should_edit("no_items_text"):
        module.case_details.short.no_items_text[lang] = request.POST.get("no_items_text")
    if should_edit("case_type"):
        case_type = request.POST.get("case_type", None)
        if case_type == USERCASE_TYPE and not isinstance(module, AdvancedModule):
            raise AppMisconfigurationError('"{}" is a reserved case type'.format(USERCASE_TYPE))
        elif case_type and not is_valid_case_type(case_type, module):
            raise AppMisconfigurationError("case type is improperly formatted")
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
    if should_edit("report_context_tile"):
        module["report_context_tile"] = request.POST.get("report_context_tile") == "true"
    if should_edit("display_style"):
        module["display_style"] = request.POST.get("display_style")
    if should_edit("source_module_id") and module["source_module_id"] != request.POST.get("source_module_id"):
        module["source_module_id"] = request.POST.get("source_module_id")
        if handle_shadow_child_modules(app, module):
            # Reload the page to show new shadow child modules
            resp['redirect'] = reverse('view_module', args=[domain, app_id, module_unique_id])
    if should_edit("display_separately"):
        module["display_separately"] = json.loads(request.POST.get("display_separately"))
    if should_edit("parent_module"):
        parent_module = request.POST.get("parent_module")
        module.parent_select.module_id = parent_module
        if module_case_hierarchy_has_circular_reference(module):
            raise AppMisconfigurationError(_("The case hierarchy contains a circular reference."))
    if should_edit("auto_select_case"):
        module["auto_select_case"] = request.POST.get("auto_select_case") == 'true'

    if app.enable_module_filtering and should_edit('module_filter'):
        module['module_filter'] = request.POST.get('module_filter')

    if should_edit('case_list_form_id'):
        module.case_list_form.form_id = request.POST.get('case_list_form_id')
    if should_edit('case_list_form_label'):
        module.case_list_form.label[lang] = request.POST.get('case_list_form_label')
    if should_edit('case_list_form_expression'):
        module.case_list_form.relevancy_expression = request.POST.get('case_list_form_expression')
    if should_edit('case_list_post_form_workflow'):
        module.case_list_form.post_form_workflow = request.POST.get('case_list_post_form_workflow')

    if should_edit("name"):
        name = request.POST.get("name", None)
        module["name"][lang] = name
        resp['update'] = {'.variable-module_name': clean_trans(module.name, [lang])}
    if should_edit('comment'):
        module.comment = request.POST.get('comment')
    for SLUG in ('case_list', 'task_list'):
        show = '{SLUG}-show'.format(SLUG=SLUG)
        label = '{SLUG}-label'.format(SLUG=SLUG)
        if request.POST.get(show) == 'true' and (request.POST.get(label) == ''):
            # Show item, but empty label, was just getting ignored
            raise AppMisconfigurationError("A label is required for {SLUG}".format(SLUG=SLUG))
        if should_edit(SLUG):
            module[SLUG].show = json.loads(request.POST[show])
            module[SLUG].label[lang] = request.POST[label]

    if should_edit("root_module_id"):
        # Make this a child module of 'root_module_id'
        old_root = module['root_module_id']
        if not request.POST.get("root_module_id"):
            module["root_module_id"] = None
        else:
            module["root_module_id"] = request.POST.get("root_module_id")

        # Add or remove children of shadows as required
        shadow_parents = (
            m for m in app.get_modules()
            if m.module_type == "shadow"
            and (m.source_module_id == request.POST.get("root_module_id") or m.source_module_id == old_root)
        )
        for shadow_parent in shadow_parents:
            if handle_shadow_child_modules(app, shadow_parent):
                resp['redirect'] = reverse('view_module', args=[domain, app_id, module_unique_id])

        if not old_root and module['root_module_id']:
            track_workflow(request.couch_user.username, "User associated module with a parent")
        elif old_root and not module['root_module_id']:
            track_workflow(request.couch_user.username, "User orphaned a child module")

    if should_edit('additional_case_types'):
        module.search_config.additional_case_types = list(set(request.POST.getlist('additional_case_types')))

    if should_edit('excl_form_ids') and isinstance(module, ShadowModule):
        excl = request.POST.getlist('excl_form_ids')
        excl.remove('0')  # Placeholder value to make sure excl_form_ids is POSTed when no forms are excluded
        module.excluded_form_ids = excl

    if should_edit('form_session_endpoints') or \
            should_edit('session_endpoint_id') and isinstance(module, ShadowModule):
        raw_endpoint_id = request.POST['session_endpoint_id']
        mappings = request.POST.getlist('form_session_endpoints')
        set_shadow_module_and_form_session_endpoint(
            module, raw_endpoint_id, [json.loads(m) for m in mappings], app)

    elif should_edit('session_endpoint_id'):
        raw_endpoint_id = request.POST['session_endpoint_id']
        set_session_endpoint(module, raw_endpoint_id, app)

    if should_edit('case_list_session_endpoint_id'):
        raw_endpoint_id = request.POST['case_list_session_endpoint_id']
        set_case_list_session_endpoint(module, raw_endpoint_id, app)

    if should_edit('lazy_load_case_list_fields'):
        module["lazy_load_case_list_fields"] = request.POST.get("lazy_load_case_list_fields") == 'true'

    if should_edit('custom_assertions'):
        module.custom_assertions = validate_custom_assertions(
            request.POST.get('custom_assertions'),
            module.custom_assertions,
            lang,
        )

    handle_media_edits(request, module, should_edit, resp, lang)
    handle_media_edits(request, module.case_list_form, should_edit, resp, lang, prefix='case_list_form_')
    if hasattr(module, 'case_list'):
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
        for report in get_report_and_registry_report_configs_for_domain(domain)
    ]
    app.save()
    return back_to_main(request, domain, app_id=app.id, module_id=module.id)


def _new_shadow_module(request, domain, app, name, lang, shadow_module_version=2):
    module = app.add_module(ShadowModule.new_module(name, lang, shadow_module_version=shadow_module_version))
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
    deletion_records = []

    app = get_app(domain, app_id)
    try:
        module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundException:
        return bail(request, domain, app_id)
    if module.get_child_modules():
        if module.module_type == 'shadow':
            # When deleting a shadow module, delete all the shadow-children
            for child_module in module.get_child_modules():
                deletion_records.append(app.delete_module(child_module.unique_id))
        else:
            messages.error(request, _('"{}" has sub-menus. You must remove these before '
                                      'you can delete it.').format(module.default_name()))
            return back_to_main(request, domain, app_id)

    shadow_children = [
        m.unique_id for m in app.get_modules()
        if m.module_type == 'shadow' and m.source_module_id == module_unique_id and m.root_module_id is not None
    ]
    for shadow_child in shadow_children:
        # We don't allow directly deleting or editing the source of a shadow
        # child, so we delete it when its source is deleted
        deletion_records.append(app.delete_module(shadow_child))

    deletion_records.append(app.delete_module(module_unique_id))
    restore_url = "{}?{}".format(
        reverse('undo_delete_module', args=[domain]),
        "&".join("record_id={}".format(record.get_id) for record in deletion_records)
    )
    deleted_names = ", ".join(record.module.default_name(app=app) for record in deletion_records)
    messages.success(
        request,
        _('You have deleted "{deleted_names}". <a href="{restore_url}" class="post-link">Undo</a>').format(
            deleted_names=deleted_names, restore_url=restore_url),
        extra_tags='html'
    )
    app.save()
    clear_xmlns_app_id_cache(domain)
    return back_to_main(request, domain, app_id=app_id)


@no_conflict_require_POST
@require_can_edit_apps
def undo_delete_module(request, domain):
    module_names = []
    app = None
    for record_id in request.GET.getlist('record_id'):
        record = DeleteModuleRecord.get(record_id)
        record.undo()
        app = app or Application.get(record.app_id)
        module_names.append(record.module.default_name(app=app))
    messages.success(request, f'Module {", ".join(module_names)} successfully restored.')
    return back_to_main(request, domain, app_id=record.app_id, module_id=record.module_id)


@require_can_edit_apps
def upgrade_shadow_module(request, domain, app_id, module_unique_id):
    app = get_app(domain, app_id)
    try:
        shadow_module = app.get_module_by_unique_id(module_unique_id)
    except ModuleNotFoundError:
        messages.error(request, "Couldn't find module")
    else:
        if shadow_module.shadow_module_version == 1:
            shadow_module.shadow_module_version = 2
            handle_shadow_child_modules(app, shadow_module)
            messages.success(request, 'Module successfully upgraded.')
        else:
            messages.error(request, "Can't upgrade this module, it's already at the new version")

    return back_to_main(request, domain, app_id=app_id, module_unique_id=module_unique_id)


@no_conflict_require_POST
@require_can_edit_apps
def overwrite_module_case_list(request, domain, app_id, module_unique_id):
    app = get_app(domain, app_id)
    dest_module_unique_ids = request.POST.getlist('dest_module_unique_ids')
    src_module = app.get_module_by_unique_id(module_unique_id)
    detail_type = request.POST['detail_type']

    # For short details, user selects which properties to copy.
    # For long details, all properties are copied.
    short_attrs = {
        'columns',
        'filter',
        'sort_elements',
        'custom_variables',
        'custom_xml',
        'case_tile_configuration',
        'multi_select',
        'print_template',
        'search_properties',
        'search_default_properties',
        'search_claim_options',
    }
    short_attrs = {a for a in short_attrs if request.POST.get(a) == 'on'}
    if 'multi_select' in short_attrs:
        short_attrs.update({'auto_select', 'max_select_value'})

    error_list = _validate_overwrite_request(request, detail_type, dest_module_unique_ids, short_attrs)
    if error_list:
        for err in error_list:
            messages.error(request, err)
        return back_to_main(request, domain, app_id=app_id, module_unique_id=module_unique_id)

    for dest_module_unique_id in dest_module_unique_ids:
        dest_module = app.get_module_by_unique_id(dest_module_unique_id)
        if dest_module.case_type != src_module.case_type:
            messages.error(request, _("Case type {} does not match current menu.").format(src_module.case_type))
        else:
            try:
                if detail_type == "short":
                    _update_module_short_detail(src_module, dest_module, short_attrs)
                else:
                    _update_module_long_detail(src_module, dest_module)
                messages.success(request, _("Updated {}").format(dest_module.default_name()))
            except Exception:
                notify_exception(
                    request,
                    message=f'Error in updating module: {dest_module.default_name()}',
                    details={'domain': domain, 'app_id': app_id, }
                )
                messages.error(request, _("Could not update {}").format(dest_module.default_name()))

    app.save()
    return back_to_main(request, domain, app_id=app_id, module_unique_id=module_unique_id)


def _validate_overwrite_request(request, detail_type, dest_modules, short_attrs):
    assert detail_type in ['short', 'long']
    error_list = []

    if not dest_modules:
        error_list.append(_("Please choose at least one menu to overwrite."))
    if detail_type == 'short':
        if not short_attrs:
            error_list.append(_("Please choose at least one option to overwrite."))
    return error_list


# attrs may contain a both top-level Detail attributes and attributes that
# belong to the detail's search config with should be prefixed with "search_"
def _update_module_short_detail(src_module, dest_module, attrs):
    search_attrs = {a for a in attrs if a.startswith('search_')}
    if search_attrs:
        _update_module_search_config(src_module, dest_module, search_attrs)

    attrs = attrs - search_attrs
    src_detail = Detail.wrap(getattr(src_module.case_details, "short").to_json().copy())

    # Shadow modules inherit some attributes from source module, so ignore the detail attr
    if src_module.module_type == "shadow":
        if 'multi_select' in attrs:
            src_detail.multi_select = src_module.is_multi_select()
            src_detail.auto_select = src_module.is_auto_select()
            src_detail.max_select_value = src_module.max_select_value

    if attrs:
        dest_detail = getattr(dest_module.case_details, "short")
        dest_detail.overwrite_attrs(src_detail, attrs)


def _update_module_search_config(src_module, dest_module, search_attrs):
    src_config = src_module.search_config
    dest_config = dest_module.search_config
    dest_config.overwrite_attrs(src_config, search_attrs)


def _update_module_long_detail(src_module, dest_module):
    setattr(dest_module.case_details, "long", getattr(src_module.case_details, "long"))


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
    ... ]  # Incoming search properties' labels/hints are not dictionaries
    >>> lang = 'en'
    >>> list(_update_search_properties(module, search_properties, lang)) == [
    ...     {'name': 'name', 'label': {'fr': 'Nom', 'en': 'Name'}},
    ...     {'name': 'dob'. 'label': {'en': 'Date of birth'}},
    ... ]  # English label is added, "age" property is dropped
    True

    """

    # Replace translation for current language in a translations dict
    def _update_translation(old_obj, new_data, old_attr, new_attr=None):
        new_attr = new_attr or old_attr
        values = getattr(old_obj, old_attr) if old_obj else {}
        values.pop(lang, None)
        new_value = new_data.get(new_attr)
        if new_value:
            values[lang] = new_value
        return values

    def _get_itemset(prop):
        fixture_props = json.loads(prop['fixture'])
        keys = {'instance_id', 'nodeset', 'label', 'value', 'sort'}
        missing = [key for key in keys if not fixture_props.get(key)]
        if missing:
            raise CaseSearchConfigError(_("""
                The case search property '{}' is missing the following lookup table attributes: {}
            """).format(prop['name'], ", ".join(missing)))
        return {key: fixture_props[key] for key in keys}

    props_by_name = {p.name: p for p in module.search_config.properties}
    for prop in search_properties:
        current = props_by_name.get(prop['name'])

        ret = {
            'name': prop['name'],
            'label': _update_translation(current, prop, 'label'),
            'hint': _update_translation(current, prop, 'hint'),
        }
        if prop.get('default_value'):
            ret['default_value'] = prop['default_value']
        if prop.get('hidden'):
            ret['hidden'] = prop['hidden']
        if prop.get('allow_blank_value'):
            ret['allow_blank_value'] = prop['allow_blank_value']
        if prop.get('exclude'):
            ret['exclude'] = prop['exclude']
        if prop.get('required_test'):
            ret['required'] = {
                'test': prop['required_test'],
                'text': _update_translation(current.required if current else None, prop, "text", "required_text"),
            }
        if prop.get('validation_test'):
            ret['validations'] = [{
                'test': prop['validation_test'],
                'text': _update_translation(current.validations[0] if current and current.validations else None,
                                            prop, "text", "validation_text"),
            }]
        if prop.get('is_group'):
            ret['is_group'] = prop['is_group']
        if prop.get('group_key'):
            ret['group_key'] = prop['group_key']
        if prop.get('appearance', '') == 'fixture':
            if prop.get('is_multiselect', False):
                ret['input_'] = 'select'
                ret['default_value'] = prop['default_value']
            else:
                ret['input_'] = 'select1'
            ret['itemset'] = _get_itemset(prop)
        elif prop.get('appearance', '') == 'checkbox':
            ret['input_'] = 'checkbox'
            ret['itemset'] = _get_itemset(prop)
        elif prop.get('appearance', '') == 'barcode_scan':
            ret['appearance'] = 'barcode_scan'
        elif prop.get('appearance', '') == 'address':
            ret['appearance'] = 'address'
        elif prop.get('appearance', '') in ('date', 'daterange'):
            ret['input_'] = prop['appearance']

        if prop.get('appearance', '') == 'fixture' or not prop.get('appearance', ''):
            ret['receiver_expression'] = prop.get('receiver_expression', '')

        yield ret


@waf_allow('XSS_BODY')
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
    case_tile_template = params.get('caseTileTemplate', None)
    print_template = params.get('printTemplate', None)
    custom_variables_dict = {
        'short': params.get("short_custom_variables_dict", None),
        'long': params.get("long_custom_variables_dict", None)
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
            return HttpResponseBadRequest(format_html("Unknown detail type '{}'", detail_type))

    lang = request.COOKIES.get('lang', app.langs[0])
    _update_short_details(detail, short, params, lang)

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
    if case_tile_template is not None:
        if short is not None:
            detail.short.case_tile_template = case_tile_template
        else:
            detail.long.case_tile_template = case_tile_template
    if custom_xml is not None:
        detail.short.custom_xml = custom_xml

    if custom_variables_dict['short'] is not None:
        detail.short.custom_variables_dict = custom_variables_dict['short']
    if custom_variables_dict['long'] is not None:
        detail.long.custom_variables_dict = custom_variables_dict['long']

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

    _gather_and_update_search_properties(params, app, module, lang)

    resp = {}
    app.save(resp)
    return JsonResponse(resp)


def _gather_and_update_search_properties(params, app, module, lang):
    search_properties = params.get("search_properties")

    def _has_search_properties(search_properties):
        if search_properties is not None:
            has_properties = search_properties.get('properties') is not None
            has_default_properties = search_properties.get('default_properties') is not None
            return has_properties or has_default_properties
        return False

    if _has_search_properties(search_properties):
        title_label = module.search_config.title_label
        title_label[lang] = search_properties.get('title_label', '')

        description = module.search_config.description
        description[lang] = search_properties.get('description', '')

        search_label = module.search_config.search_label
        search_label.label[lang] = search_properties.get('search_label', '')
        if search_properties.get('search_label_image_for_all'):
            search_label.use_default_image_for_all = (
                search_properties.get('search_label_image_for_all') == 'true')
        if search_properties.get('search_label_audio_for_all'):
            search_label.use_default_audio_for_all = (
                search_properties.get('search_label_audio_for_all') == 'true')
        search_label.set_media("media_image", lang, search_properties.get('search_label_image'))
        search_label.set_media("media_audio", lang, search_properties.get('search_label_audio'))

        search_again_label = module.search_config.search_again_label
        search_again_label.label[lang] = search_properties.get('search_again_label', '')
        if search_properties.get('search_again_label_image_for_all'):
            search_again_label.use_default_image_for_all = (
                search_properties.get('search_again_label_image_for_all') == 'true')
        if search_properties.get('search_again_label_audio_for_all'):
            search_again_label.use_default_audio_for_all = (
                search_properties.get('search_again_label_audio_for_all') == 'true')
        search_again_label.set_media("media_image", lang, search_properties.get('search_again_label_image'))
        search_again_label.set_media("media_audio", lang, search_properties.get('search_again_label_audio'))

        try:
            properties = [
                CaseSearchProperty.wrap(p)
                for p in _update_search_properties(
                    module,
                    search_properties.get('properties'), lang
                )
            ]
        except CaseSearchConfigError as e:
            return HttpResponseBadRequest(e)
        xpath_props = [
            "search_filter", "blacklisted_owner_ids_expression",
            "search_button_display_condition", "additional_relevant"
        ]

        def _check_xpath(xpath, location):
            is_valid, message = validate_xpath(xpath)
            if not is_valid:
                raise ValueError(
                    f"Please fix the errors in xpath expression '{xpath}' "
                    f"in {location}. The error is {message}"
                )

        for prop in xpath_props:
            xpath = search_properties.get(prop, "")
            if xpath:
                try:
                    _check_xpath(xpath, "Search and Claim Options")
                except ValueError as e:
                    return HttpResponseBadRequest(str(e))

        additional_registry_cases = []
        for case_id_xpath in search_properties.get('additional_registry_cases', []):
            if not case_id_xpath:
                continue

            try:
                _check_xpath(case_id_xpath, "the Case ID of Additional Data Registry Query")
            except ValueError as e:
                return HttpResponseBadRequest(str(e))

            additional_registry_cases.append(case_id_xpath)

        data_registry_slug = search_properties.get('data_registry', "")
        data_registry_workflow = search_properties.get('data_registry_workflow', "")
        # force auto launch when data registry load case workflow selected
        force_auto_launch = data_registry_slug and data_registry_workflow == REGISTRY_WORKFLOW_LOAD_CASE

        instance_name = search_properties.get('instance_name', "")
        if instance_name and not re.match(r"^[a-zA-Z]\w*$", instance_name):
            return HttpResponseBadRequest(_(
                "'{}' is an invalid instance name. It can contain only letters, numbers, and underscores."
            ).format(instance_name))

        module.search_config = CaseSearch(
            search_label=search_label,
            search_again_label=search_again_label,
            title_label=title_label,
            description=description,
            properties=properties,
            additional_case_types=module.search_config.additional_case_types,
            additional_relevant=search_properties.get('additional_relevant', ''),
            auto_launch=force_auto_launch or bool(search_properties.get('auto_launch')),
            default_search=bool(search_properties.get('default_search')),
            search_filter=search_properties.get('search_filter', ""),
            search_button_display_condition=search_properties.get('search_button_display_condition', ""),
            blacklisted_owner_ids_expression=search_properties.get('blacklisted_owner_ids_expression', ""),
            default_properties=[
                DefaultCaseSearchProperty.wrap(p)
                for p in search_properties.get('default_properties')
            ],
            custom_sort_properties=[
                CaseSearchCustomSortProperty.wrap(p)
                for p in search_properties.get('custom_sort_properties')
            ],
            data_registry=data_registry_slug,
            data_registry_workflow=data_registry_workflow,
            additional_registry_cases=additional_registry_cases,
            custom_related_case_property=search_properties.get('custom_related_case_property', ""),
            inline_search=search_properties.get('inline_search', False),
            instance_name=instance_name,
            include_all_related_cases=search_properties.get('include_all_related_cases', False),
            dynamic_search=app.split_screen_dynamic_search and not module.is_auto_select(),
            search_on_clear=search_properties.get('search_on_clear', False),
        )


def _update_short_details(detail, short, params, lang):
    if short is not None:
        detail.short.columns = list(map(DetailColumn.from_json, short))
        detail.short.multi_select = params.get('multi_select', None)
        detail.short.auto_select = params.get('auto_select', None)
        detail.short.max_select_value = params.get('max_select_value') or MULTI_SELECT_MAX_SELECT_VALUE
        persist_case_context = params.get('persistCaseContext', None)
        if persist_case_context is not None:
            detail.short.persist_case_context = persist_case_context
            detail.short.persistent_case_context_xml = params.get('persistentCaseContextXML', None)

        def _set_if_not_none(param_name, attribute_name=None):
            value = params.get(param_name, None)
            if value is not None:
                setattr(detail.short, attribute_name or param_name, value)

        _set_if_not_none('persistTileOnForms', 'persist_tile_on_forms')
        _set_if_not_none('persistentCaseTileFromModule', 'persistent_case_tile_from_module')
        _set_if_not_none('enableTilePullDown', 'pull_down_tile')

        case_tile_group = params.get('case_tile_group', None)
        if case_tile_group is not None:
            detail.short.case_tile_group = CaseTileGroupConfig(
                index_identifier=case_tile_group['index_identifier'],
                header_rows=int(case_tile_group['header_rows'])
            )

        case_list_lookup = params.get("case_list_lookup", None)
        if case_list_lookup is not None:
            _save_case_list_lookup_params(detail.short, case_list_lookup, lang)


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
    module.report_context_tile = params['report_context_tile']

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

    try:
        app.save()
    except Exception:
        notify_exception(
            request,
            message="Something went wrong while saving app {} while editing report modules".format(app_id),
            details={'domain': domain, 'app_id': app_id, }
        )
        return HttpResponseBadRequest(_("There was a problem processing your request."))

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
        'app': app,
        'build_errors': errors,
        'not_actual_build': True,
        'domain': domain,
        'langs': langs,
        'toggles': toggles_enabled_for_request(request),
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
        'xmlns_uuid': generate_xmlns(),
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
        name_update=ConditionalCaseUpdate(question_path="/data/name"),
        condition=FormActionCondition(type='always'),
    )
    enroll.actions.update_case = UpdateCaseAction(
        update={
            'simprintsId': ConditionalCaseUpdate(question_path='/data/simprintsId'),
            'rightIndex': ConditionalCaseUpdate(question_path='/data/rightIndex'),
            'rightThumb': ConditionalCaseUpdate(question_path='/data/rightThumb'),
            'leftIndex': ConditionalCaseUpdate(question_path='/data/leftIndex'),
            'leftThumb': ConditionalCaseUpdate(question_path='/data/leftThumb'),
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

    output_tag = mark_safe(  # nosec: no user input
        "<output value=\"instance('casedb')/casedb/case[@case_id = "
        "instance('commcaresession')/session/data/case_id]/case_name\" "
        "vellum:value=\"#case/case_name\" />"
    )

    context = {
        'xmlns_uuid': generate_xmlns(),
        'form_name': form_name,
        'lang': lang,
        'placeholder_label': format_html(_(
            "This is your follow up form for {}. Delete this label and add "
            "questions for any follow up visits."
        ), output_tag)
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
            'existing_case_types': list(get_case_types_for_domain_es(domain)),
            'deprecated_case_types': list(get_data_dict_deprecated_case_types(domain))
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
    'shadow-v1': {
        FN: partial(_new_shadow_module, shadow_module_version=1),
        VALIDATIONS: []
    },
    'training': {
        FN: _new_training_module,
        VALIDATIONS: []
    },
}
