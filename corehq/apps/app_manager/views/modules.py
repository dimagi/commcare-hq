# coding=utf-8
import os
from collections import OrderedDict, namedtuple
import json
import logging
from lxml import etree

from django.template.loader import render_to_string
from django.utils.translation import ugettext as _, gettext_lazy
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.views.decorators.http import require_GET
from django.contrib import messages
from corehq.apps.app_manager.views.media_utils import process_media_attribute, \
    handle_media_edits
from corehq.apps.case_search.models import case_search_enabled_for_domain
from corehq.apps.reports.daterange import get_simple_dateranges

from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.views.utils import back_to_main, bail, get_langs
from corehq import toggles, feature_previews
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.const import (
    CAREPLAN_GOAL,
    CAREPLAN_TASK,
    USERCASE_TYPE,
    APP_V1,
    CLAIM_DEFAULT_RELEVANT_CONDITION,
)
from corehq.apps.app_manager.util import (
    is_valid_case_type,
    is_usercase_in_use,
    get_per_type_defaults,
    ParentCasePropertyBuilder,
    prefix_usercase_properties,
    commtrack_ledger_sections,
    module_offers_search,
    module_case_hierarchy_has_circular_reference, get_app_manager_template)
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.userreports.models import ReportConfiguration, \
    StaticReportConfiguration
from dimagi.utils.web import json_response, json_request
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import (
    AdvancedModule,
    CareplanModule,
    CaseSearch,
    CaseSearchProperty,
    DeleteModuleRecord,
    DetailColumn,
    DetailTab,
    FormActionCondition,
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
    DefaultCaseSearchProperty, get_all_mobile_filter_configs, get_auto_filter_configurations)
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps

logger = logging.getLogger(__name__)


def get_module_template(domain, module):
    if isinstance(module, CareplanModule):
        return get_app_manager_template(
            domain,
            "app_manager/v1/module_view_careplan.html",
            "app_manager/v2/module_view_careplan.html",
        )
    elif isinstance(module, AdvancedModule):
        return get_app_manager_template(
            domain,
            "app_manager/v1/module_view_advanced.html",
            "app_manager/v2/module_view_advanced.html",
        )
    elif isinstance(module, ReportModule):
        return get_app_manager_template(
            domain,
            'app_manager/v1/module_view_report.html',
            'app_manager/v2/module_view_report.html',
        )
    else:
        return get_app_manager_template(
            domain,
            "app_manager/v1/module_view.html",
            "app_manager/v2/module_view.html",
        )


def get_module_view_context(app, module, lang=None):
    # shared context
    context = {
        'edit_name_url': reverse(
            'edit_module_attr',
            args=[app.domain, app.id, module.id, 'name']
        )
    }
    if isinstance(module, CareplanModule):
        context.update(_get_careplan_module_view_context(app, module))
    elif isinstance(module, AdvancedModule):
        context.update(_get_advanced_module_view_context(app, module, lang))
    elif isinstance(module, ReportModule):
        context.update(_get_report_module_context(app, module))
    else:
        context.update(_get_basic_module_view_context(app, module, lang))
    if isinstance(module, ShadowModule):
        context.update(_get_shadow_module_view_context(app, module, lang))
    return context


def _get_careplan_module_view_context(app, module):
    case_property_builder = _setup_case_property_builder(app)
    subcase_types = list(app.get_subcase_types(module.case_type))
    return {
        'parent_modules': _get_parent_modules(app, module,
                                             case_property_builder,
                                             CAREPLAN_GOAL),
        'details': [
            {
                'label': gettext_lazy('Goal List'),
                'detail_label': gettext_lazy('Goal Detail'),
                'type': 'careplan_goal',
                'model': 'case',
                'properties': sorted(
                    case_property_builder.get_properties(CAREPLAN_GOAL)),
                'sort_elements': module.goal_details.short.sort_elements,
                'short': module.goal_details.short,
                'long': module.goal_details.long,
                'subcase_types': subcase_types,
            },
            {
                'label': gettext_lazy('Task List'),
                'detail_label': gettext_lazy('Task Detail'),
                'type': 'careplan_task',
                'model': 'case',
                'properties': sorted(
                    case_property_builder.get_properties(CAREPLAN_TASK)),
                'sort_elements': module.task_details.short.sort_elements,
                'short': module.task_details.short,
                'long': module.task_details.long,
                'subcase_types': subcase_types,
            },
        ],
    }


def _get_advanced_module_view_context(app, module, lang=None):
    case_property_builder = _setup_case_property_builder(app)
    case_type = module.case_type
    form_options = _case_list_form_options(app, module, case_type, lang)
    return {
        'fixture_columns_by_type': _get_fixture_columns_by_type(app.domain),
        'details': _get_module_details_context(app, module,
                                               case_property_builder,
                                               case_type),
        'case_list_form_options': form_options,
        'case_list_form_not_allowed_reason': _case_list_form_not_allowed_reason(
            module),
        'valid_parent_modules': [
            parent_module for parent_module in app.modules
            if not getattr(parent_module, 'root_module_id', None)
        ],
        'child_module_enabled': True,
        'is_search_enabled': case_search_enabled_for_domain(app.domain),
        'search_properties': module.search_config.properties if module_offers_search(module) else [],
        'include_closed': module.search_config.include_closed if module_offers_search(module) else False,
        'default_properties': module.search_config.default_properties if module_offers_search(module) else [],
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


def _get_basic_module_view_context(app, module, lang=None):
    case_property_builder = _setup_case_property_builder(app)
    case_type = module.case_type
    form_options = _case_list_form_options(app, module, case_type, lang)
    # http://manage.dimagi.com/default.asp?178635
    allow_with_parent_select = app.build_version >= '2.23' or not module.parent_select.active
    allow_case_list_form = _case_list_form_not_allowed_reason(
        module,
        AllowWithReason(allow_with_parent_select, AllowWithReason.PARENT_SELECT_ACTIVE)
    )
    return {
        'parent_modules': _get_parent_modules(app, module, case_property_builder, case_type),
        'fixture_columns_by_type': _get_fixture_columns_by_type(app.domain),
        'details': _get_module_details_context(app, module, case_property_builder, case_type),
        'case_list_form_options': form_options,
        'case_list_form_not_allowed_reason': allow_case_list_form,
        'valid_parent_modules': _get_valid_parent_modules(app, module),
        'child_module_enabled': (
            toggles.BASIC_CHILD_MODULE.enabled(app.domain) and module.doc_type != "ShadowModule"
        ),
        'is_search_enabled': case_search_enabled_for_domain(app.domain),
        'search_properties': module.search_config.properties if module_offers_search(module) else [],
        'include_closed': module.search_config.include_closed if module_offers_search(module) else False,
        'default_properties': module.search_config.default_properties if module_offers_search(module) else [],
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
        'modules': [get_mod_dict(m) for m in app.modules if m.module_type in ['basic', 'advanced']],
        'excluded_form_ids': module.excluded_form_ids,
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
    warnings = []
    validity = module.check_report_validity()

    # We're now proactively deleting these references, so after that's been
    # out for a while, this can be removed (say June 2016 or later)
    if not validity.is_valid:
        module.report_configs = validity.valid_report_configs
        warnings.append(
            gettext_lazy('Your app contains references to reports that are '
                         'deleted. These will be removed on save.')
        )

    filter_choices = [
        {'slug': f.doc_type, 'description': f.short_description} for f in get_all_mobile_filter_configs()
    ]
    auto_filter_choices = [
        {'slug': f.slug, 'description': f.short_description} for f in get_auto_filter_configurations()

    ]
    return {
        'all_reports': [_report_to_config(r) for r in all_reports],
        'current_reports': [r.to_json() for r in module.report_configs],
        'warnings': warnings,
        'filter_choices': filter_choices,
        'auto_filter_choices': auto_filter_choices,
        'daterange_choices': [choice._asdict() for choice in get_simple_dateranges()],
    }


def _get_fixture_columns_by_type(domain):
    return {
        fixture.tag: [field.field_name for field in fixture.fields]
        for fixture in FixtureDataType.by_domain(domain)
    }


def _setup_case_property_builder(app):
    defaults = ('name', 'date-opened', 'status', 'last_modified')
    if app.case_sharing:
        defaults += ('#owner_name',)
    per_type_defaults = None
    if is_usercase_in_use(app.domain):
        per_type_defaults = get_per_type_defaults(app.domain, [USERCASE_TYPE])
    builder = ParentCasePropertyBuilder(app, defaults=defaults,
                                        per_type_defaults=per_type_defaults)
    return builder


def _get_parent_modules(app, module, case_property_builder, case_type_):
        parent_types = case_property_builder.get_parent_types(case_type_)
        modules = app.modules
        parent_module_ids = [mod.unique_id for mod in modules
                             if mod.case_type in parent_types]
        return [{
            'unique_id': mod.unique_id,
            'name': mod.name,
            'is_parent': mod.unique_id in parent_module_ids,
        } for mod in app.modules if mod.case_type != case_type_ and mod.unique_id != module.unique_id]


def _get_valid_parent_modules(app, module):
    return [parent_module for parent_module in app.modules
            if not getattr(parent_module, 'root_module_id', None)
            and not parent_module == module and parent_module.doc_type != "ShadowModule"]


def _case_list_form_options(app, module, case_type_, lang=None):
    options = OrderedDict()
    forms = [
        form
        for mod in app.get_modules() if module.unique_id != mod.unique_id
        for form in mod.get_forms() if form.is_registration_form(case_type_)
    ]
    options['disabled'] = gettext_lazy("Don't Show")
    langs = None if lang is None else [lang]
    options.update({f.unique_id: trans(f.name, langs) for f in forms})

    return options


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
                'properties': ['name'] + commtrack_ledger_sections(app.commtrack_requisition_mode),
                'sort_elements': module.product_details.short.sort_elements,
                'short': module.product_details.short,
                'subcase_types': subcase_types,
            })
    else:
        item['parent_select'] = module.parent_select
        details = [item]

    return details


def _case_list_form_not_allowed_reason(module, allow=None):
    if allow and not allow.allow:
        return allow
    elif not module.all_forms_require_a_case():
        return AllowWithReason(False, AllowWithReason.ALL_FORMS_REQUIRE_CASE)
    elif module.put_in_root:
        return AllowWithReason(False, AllowWithReason.MODULE_IN_ROOT)
    else:
        return AllowWithReason(True, '')


class AllowWithReason(namedtuple('AllowWithReason', 'allow reason')):
    ALL_FORMS_REQUIRE_CASE = 1
    MODULE_IN_ROOT = 2
    PARENT_SELECT_ACTIVE = 3

    @property
    def message(self):
        if self.reason == self.ALL_FORMS_REQUIRE_CASE:
            return gettext_lazy('Not all forms in the case list update a case.')
        elif self.reason == self.MODULE_IN_ROOT:
            return gettext_lazy("'Menu Mode' is not configured as 'Display menu and then forms'")
        elif self.reason == self.PARENT_SELECT_ACTIVE:
            return gettext_lazy("'Parent Selection' is configured.")


@no_conflict_require_POST
@require_can_edit_apps
def edit_module_attr(request, domain, app_id, module_id, attr):
    """
    Called to edit any (supported) module attribute, given by attr
    """
    attributes = {
        "all": None,
        "auto_select_case": None,
        "case_label": None,
        "case_list": ('case_list-show', 'case_list-label'),
        "case_list-menu_item_media_audio": None,
        "case_list-menu_item_media_image": None,
        "case_list_form_id": None,
        "case_list_form_label": None,
        "case_list_form_media_audio": None,
        "case_list_form_media_image": None,
        "case_type": None,
        'comment': None,
        "display_separately": None,
        "has_schedule": None,
        "media_audio": None,
        "media_image": None,
        "module_filter": None,
        "name": None,
        "parent_module": None,
        "put_in_root": None,
        "referral_label": None,
        "root_module_id": None,
        "source_module_id": None,
        "task_list": ('task_list-show', 'task_list-label'),
        "excl_form_ids": None,
        "display_style": None
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
    module = app.get_module(module_id)
    lang = request.COOKIES.get('lang', app.langs[0])
    resp = {'update': {}, 'corrections': {}}
    if should_edit("case_type"):
        case_type = request.POST.get("case_type", None)
        if not case_type or is_valid_case_type(case_type, module):
            old_case_type = module["case_type"]
            module["case_type"] = case_type
            for cp_mod in (mod for mod in app.modules if isinstance(mod, CareplanModule)):
                if cp_mod.unique_id != module.unique_id and cp_mod.parent_select.module_id == module.unique_id:
                    cp_mod.case_type = case_type

            def rename_action_case_type(mod):
                for form in mod.forms:
                    for action in form.actions.get_all_actions():
                        if action.case_type == old_case_type:
                            action.case_type = case_type

            if isinstance(module, AdvancedModule):
                rename_action_case_type(module)
            for ad_mod in (mod for mod in app.modules if isinstance(mod, AdvancedModule)):
                if ad_mod.unique_id != module.unique_id and ad_mod.case_type != old_case_type:
                    # only apply change if the module's case_type does not reference the old value
                    rename_action_case_type(ad_mod)
        elif case_type == USERCASE_TYPE and not isinstance(module, AdvancedModule):
            return HttpResponseBadRequest('"{}" is a reserved case type'.format(USERCASE_TYPE))
        else:
            return HttpResponseBadRequest("case type is improperly formatted")
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
    if should_edit('case_list_form_media_image'):
        new_path = process_media_attribute(
            'case_list_form_media_image',
            resp,
            request.POST.get('case_list_form_media_image')
        )
        module.case_list_form.set_icon(lang, new_path)

    if should_edit('case_list_form_media_audio'):
        new_path = process_media_attribute(
            'case_list_form_media_audio',
            resp,
            request.POST.get('case_list_form_media_audio')
        )
        module.case_list_form.set_audio(lang, new_path)

    if should_edit('case_list-menu_item_media_image'):
        val = process_media_attribute(
            'case_list-menu_item_media_image',
            resp,
            request.POST.get('case_list-menu_item_media_image')
        )
        module.case_list.set_icon(lang, val)
    if should_edit('case_list-menu_item_media_audio'):
        val = process_media_attribute(
            'case_list-menu_item_media_audio',
            resp,
            request.POST.get('case_list-menu_item_media_audio')
        )
        module.case_list.set_audio(lang, val)

    for attribute in ("name", "case_label", "referral_label"):
        if should_edit(attribute):
            name = request.POST.get(attribute, None)
            module[attribute][lang] = name
            if should_edit("name"):
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
        if not request.POST.get("root_module_id"):
            module["root_module_id"] = None
        else:
            try:
                app.get_module(module_id)
                module["root_module_id"] = request.POST.get("root_module_id")
            except ModuleNotFoundException:
                messages.error(_("Unknown Menu"))

    if should_edit('excl_form_ids') and isinstance(module, ShadowModule):
        excl = request.POST.getlist('excl_form_ids')
        excl.remove('0')  # Placeholder value to make sure excl_form_ids is POSTed when no forms are excluded
        module.excluded_form_ids = excl

    handle_media_edits(request, module, should_edit, resp, lang)

    app.save(resp)
    resp['case_list-show'] = module.requires_case_details()
    return HttpResponse(json.dumps(resp))


def _new_advanced_module(request, domain, app, name, lang):
    module = app.add_module(AdvancedModule.new_module(name, lang))
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


@no_conflict_require_POST
@require_can_edit_apps
def delete_module(request, domain, app_id, module_unique_id):
    "Deletes a module from an app"
    app = get_app(domain, app_id)
    try:
        record = app.delete_module(module_unique_id)
    except ModuleNotFoundException:
        return bail(request, domain, app_id)
    if record is not None:
        messages.success(
            request,
            'You have deleted a module. <a href="%s" class="post-link">Undo</a>' % reverse(
                'undo_delete_module', args=[domain, record.get_id]
            ),
            extra_tags='html'
        )
        app.save()
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
def overwrite_module_case_list(request, domain, app_id, module_id):
    app = get_app(domain, app_id)
    source_module_id = int(request.POST['source_module_id'])
    detail_type = request.POST['detail_type']
    assert detail_type in ['short', 'long']
    source_module = app.get_module(source_module_id)
    dest_module = app.get_module(module_id)
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
    return back_to_main(request, domain, app_id=app_id, module_id=module_id)


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
def edit_module_detail_screens(request, domain, app_id, module_id):
    """
    Overwrite module case details. Only overwrites components that have been
    provided in the request. Components are short, long, filter, parent_select,
    fixture_select and sort_elements.
    """
    params = json_request(request.POST)
    detail_type = params.get('type')
    short = params.get('short', None)
    long = params.get('long', None)
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
    pull_down_tile = params.get("enableTilePullDown", None)
    case_list_lookup = params.get("case_list_lookup", None)
    search_properties = params.get("search_properties")
    custom_variables = {
        'short': params.get("short_custom_variables", None),
        'long': params.get("long_custom_variables", None)
    }

    app = get_app(domain, app_id)
    module = app.get_module(module_id)

    if detail_type == 'case':
        detail = module.case_details
    elif detail_type == CAREPLAN_GOAL:
        detail = module.goal_details
    elif detail_type == CAREPLAN_TASK:
        detail = module.task_details
    else:
        try:
            detail = getattr(module, '{0}_details'.format(detail_type))
        except AttributeError:
            return HttpResponseBadRequest("Unknown detail type '%s'" % detail_type)

    lang = request.COOKIES.get('lang', app.langs[0])
    if short is not None:
        detail.short.columns = map(DetailColumn.from_json, short)
        if persist_case_context is not None:
            detail.short.persist_case_context = persist_case_context
            detail.short.persistent_case_context_xml = persistent_case_context_xml
        if use_case_tiles is not None:
            detail.short.use_case_tiles = use_case_tiles
        if persist_tile_on_forms is not None:
            detail.short.persist_tile_on_forms = persist_tile_on_forms
        if pull_down_tile is not None:
            detail.short.pull_down_tile = pull_down_tile
        if case_list_lookup is not None:
            _save_case_list_lookup_params(detail.short, case_list_lookup, lang)

    if long is not None:
        detail.long.columns = map(DetailColumn.from_json, long)
        if tabs is not None:
            detail.long.tabs = map(DetailTab.wrap, tabs)
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

    if sort_elements is not None:
        detail.short.sort_elements = []
        for sort_element in sort_elements:
            item = SortElement()
            item.field = sort_element['field']
            item.type = sort_element['type']
            item.direction = sort_element['direction']
            item.display[lang] = sort_element['display']
            detail.short.sort_elements.append(item)
    if parent_select is not None:
        module.parent_select = ParentSelect.wrap(parent_select)
        if module_case_hierarchy_has_circular_reference(module):
            return HttpResponseBadRequest(_("The case hierarchy contains a circular reference."))
    if fixture_select is not None:
        module.fixture_select = FixtureSelect.wrap(fixture_select)
    if search_properties is not None:
        if search_properties.get('properties') is not None:
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
def edit_report_module(request, domain, app_id, module_id):
    """
    Overwrite module case details. Only overwrites components that have been
    provided in the request. Components are short, long, filter, parent_select,
    and sort_elements.
    """
    params = json_request(request.POST)
    app = get_app(domain, app_id)
    module = app.get_module(module_id)
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


def validate_module_for_build(request, domain, app_id, module_id, ajax=True):
    app = get_app(domain, app_id)
    try:
        module = app.get_module(module_id)
    except ModuleNotFoundException:
        raise Http404()
    errors = module.validate_for_build()
    lang, langs = get_langs(request, app)

    response_html = render_to_string(get_app_manager_template(
            domain,
            'app_manager/v1/partials/build_errors.html',
            'app_manager/v2/partials/build_errors.html',
        ), {
        'request': request,
        'app': app,
        'build_errors': errors,
        'not_actual_build': True,
        'domain': domain,
        'langs': langs,
        'lang': lang
    })
    if ajax:
        return json_response({'error_html': response_html})
    return HttpResponse(response_html)


@no_conflict_require_POST
@require_can_edit_apps
def new_module(request, domain, app_id):
    "Adds a module to an app"
    app = get_app(domain, app_id)
    lang = request.COOKIES.get('lang', app.langs[0])
    name = request.POST.get('name')
    module_type = request.POST.get('module_type', 'case')

    if module_type == 'case' or module_type == 'survey':  # survey option added for V2

        if toggles.APP_MANAGER_V2.enabled(domain):
            if module_type == 'case':
                name = name or 'Case List'
            else:
                name = name or 'Surveys'

        module = app.add_module(Module.new_module(name, lang))
        module_id = module.id

        form_id = None
        if toggles.APP_MANAGER_V2.enabled(domain):
            if module_type == 'case':
                # registration form
                register = app.new_form(module_id, "Register", lang)
                with open(os.path.join(
                        os.path.dirname(__file__), '..', 'static',
                        'app_manager', 'xml', 'registration_form.xml')) as f:
                    register.source = f.read()
                register.actions.open_case = OpenCaseAction(
                    condition=FormActionCondition(type='always'),
                    name_path=u'/data/name')
                register.actions.update_case = UpdateCaseAction(
                    condition=FormActionCondition(type='always'))

                # make case type unique across app
                app_case_types = set(
                    [module.case_type for module in app.modules if
                     module.case_type])
                module.case_type = 'case'
                suffix = 0
                while module.case_type in app_case_types:
                    suffix = suffix + 1
                    module.case_type = 'case-{}'.format(suffix)
            else:
                form = app.new_form(module_id, "Survey", lang)
            form_id = 0
        else:
            app.new_form(module_id, "Untitled Form", lang)

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


def _new_careplan_module(request, domain, app, name, lang):
    from corehq.apps.app_manager.util import new_careplan_module
    target_module_index = request.POST.get('target_module_id')
    target_module = app.get_module(target_module_index)
    if not target_module.case_type:
        name = target_module.name[lang]
        messages.error(request, _("Please set the case type for the target module '{name}'.".format(name=name)))
        return back_to_main(request, domain, app_id=app.id)
    module = new_careplan_module(app, name, lang, target_module)
    app.save()
    response = back_to_main(request, domain, app_id=app.id, module_id=module.id)
    response.set_cookie('suppress_build_errors', 'yes')
    messages.info(request, _('Caution: Care Plan modules are a labs feature'))
    return response


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
def view_module(request, domain, app_id, module_id):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, module_id)


FN = 'fn'
VALIDATIONS = 'validations'
MODULE_TYPE_MAP = {
    'careplan': {
        FN: _new_careplan_module,
        VALIDATIONS: [
            (lambda app: app.has_careplan_module,
             _('This application already has a Careplan module'))
        ]
    },
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
}
