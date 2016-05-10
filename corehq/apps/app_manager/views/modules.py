# coding=utf-8
from collections import OrderedDict, namedtuple
import json
import logging

from django.template.loader import render_to_string
from django.utils.translation import ugettext as _, gettext_lazy
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.views.decorators.http import require_GET
from django.contrib import messages
from corehq.apps.app_manager.views.media_utils import process_media_attribute, \
    handle_media_edits
from corehq.apps.case_search.models import case_search_enabled_for_domain

from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.views.utils import back_to_main, bail, get_langs
from corehq import toggles, feature_previews
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.const import (
    CAREPLAN_GOAL,
    CAREPLAN_TASK,
    USERCASE_TYPE,
    APP_V1)
from corehq.apps.app_manager.util import (
    is_valid_case_type,
    is_usercase_in_use,
    get_per_type_defaults,
    ParentCasePropertyBuilder,
    prefix_usercase_properties,
    commtrack_ledger_sections,
    module_offers_search,
)
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.userreports.models import ReportConfiguration
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
    Module,
    ModuleNotFoundException,
    ParentSelect,
    ReportModule,
    ShadowModule,
    SortElement,
    ReportAppConfig,
    FixtureSelect,
)
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps, require_deploy_apps

logger = logging.getLogger(__name__)


def get_module_template(module):
    if isinstance(module, CareplanModule):
        return "app_manager/module_view_careplan.html"
    elif isinstance(module, AdvancedModule):
        return "app_manager/module_view_advanced.html"
    elif isinstance(module, ReportModule):
        return 'app_manager/module_view_report.html'
    else:
        return "app_manager/module_view.html"


def get_module_view_context(app, module, lang=None):
    if isinstance(module, CareplanModule):
        return _get_careplan_module_view_context(app, module)
    elif isinstance(module, AdvancedModule):
        return _get_advanced_module_view_context(app, module, lang)
    elif isinstance(module, ReportModule):
        return _get_report_module_context(app, module)
    else:
        return _get_basic_module_view_context(app, module, lang)


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
    }


def _get_report_module_context(app, module):
    def _report_to_config(report):
        return {
            'report_id': report._id,
            'title': report.title,
            'description': report.description,
            'charts': [chart for chart in report.charts if
                       chart.type == 'multibar'],
            'filter_structure': report.filters,
        }

    all_reports = ReportConfiguration.by_domain(app.domain)
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
    return {
        'all_reports': [_report_to_config(r) for r in all_reports],
        'current_reports': [r.to_json() for r in module.report_configs],
        'warnings': warnings,
    }


def _get_fixture_columns_by_type(domain):
    return {
        fixture.tag: [field.field_name for field in fixture.fields]
        for fixture in FixtureDataType.by_domain(domain)
    }


def _setup_case_property_builder(app):
    defaults = ('name', 'date-opened', 'status')
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
            return gettext_lazy('Not all forms in the module update a case.')
        elif self.reason == self.MODULE_IN_ROOT:
            return gettext_lazy("The module's 'Menu Mode' is not configured as 'Display module and then forms'")
        elif self.reason == self.PARENT_SELECT_ACTIVE:
            return gettext_lazy("The module has 'Parent Selection' configured.")


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
        if is_valid_case_type(case_type, module):
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
    if should_edit("source_module_id"):
        module["source_module_id"] = request.POST.get("source_module_id")
    if should_edit("display_separately"):
        module["display_separately"] = json.loads(request.POST.get("display_separately"))
    if should_edit("parent_module"):
        parent_module = request.POST.get("parent_module")
        module.parent_select.module_id = parent_module
    if should_edit("auto_select_case"):
        module["auto_select_case"] = request.POST.get("auto_select_case") == 'true'

    if (feature_previews.MODULE_FILTER.enabled(app.domain) and
            app.enable_module_filtering and
            should_edit('module_filter')):
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
                resp['update'].update({'.variable-module_name': module.name[lang]})
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
                messages.error(_("Unknown Module"))

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
            description={lang: report.description},
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
            label = current[prop['name']]
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
    use_case_tiles = params.get('useCaseTiles', None)
    persist_tile_on_forms = params.get("persistTileOnForms", None)
    pull_down_tile = params.get("enableTilePullDown", None)
    case_list_lookup = params.get("case_list_lookup", None)
    search_properties = params.get("search_properties")

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

    if short is not None:
        detail.short.columns = map(DetailColumn.wrap, short)
        if persist_case_context is not None:
            detail.short.persist_case_context = persist_case_context
        if use_case_tiles is not None:
            detail.short.use_case_tiles = use_case_tiles
        if persist_tile_on_forms is not None:
            detail.short.persist_tile_on_forms = persist_tile_on_forms
        if pull_down_tile is not None:
            detail.short.pull_down_tile = pull_down_tile
        if case_list_lookup is not None:
            _save_case_list_lookup_params(detail.short, case_list_lookup)

    if long is not None:
        detail.long.columns = map(DetailColumn.wrap, long)
        if tabs is not None:
            detail.long.tabs = map(DetailTab.wrap, tabs)
    if filter != ():
        # Note that we use the empty tuple as the sentinel because a filter
        # value of None represents clearing the filter.
        detail.short.filter = filter
    if custom_xml is not None:
        detail.short.custom_xml = custom_xml
    if sort_elements is not None:
        detail.short.sort_elements = []
        for sort_element in sort_elements:
            item = SortElement()
            item.field = sort_element['field']
            item.type = sort_element['type']
            item.direction = sort_element['direction']
            detail.short.sort_elements.append(item)
    if parent_select is not None:
        module.parent_select = ParentSelect.wrap(parent_select)
    if fixture_select is not None:
        module.fixture_select = FixtureSelect.wrap(fixture_select)
    # TODO: Deepcopy failing on app.save(). FB 225441
    # if search_properties is not None:
    #     lang = request.COOKIES.get('lang', app.langs[0])
    #     module.search_config = CaseSearch(properties=[
    #         CaseSearchProperty.wrap(p) for p in _update_search_properties(module, search_properties, lang)
    #     ])
    #     # TODO: Add UI and controller support for CaseSearch.command_label

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

    if (feature_previews.MODULE_FILTER.enabled(domain) and
            app.enable_module_filtering):
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

    response_html = render_to_string('app_manager/partials/build_errors.html', {
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
    if module_type == 'case':
        module = app.add_module(Module.new_module(name, lang))
        module_id = module.id
        app.new_form(module_id, "Untitled Form", lang)
        app.save()
        response = back_to_main(request, domain, app_id=app_id, module_id=module_id)
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


def _save_case_list_lookup_params(short, case_list_lookup):
    short.lookup_enabled = case_list_lookup.get("lookup_enabled", short.lookup_enabled)
    short.lookup_action = case_list_lookup.get("lookup_action", short.lookup_action)
    short.lookup_name = case_list_lookup.get("lookup_name", short.lookup_name)
    short.lookup_extras = case_list_lookup.get("lookup_extras", short.lookup_extras)
    short.lookup_responses = case_list_lookup.get("lookup_responses", short.lookup_responses)
    short.lookup_image = case_list_lookup.get("lookup_image", short.lookup_image)


@require_GET
@require_deploy_apps
def view_module(request, domain, app_id, module_id):
    from corehq.apps.app_manager.views.view_generic import view_generic
    return view_generic(request, domain, app_id, module_id)


common_module_validations = [
    (lambda app: app.application_version == APP_V1,
     _('Please upgrade you app to > 2.0 in order to add this module'))
]

FN = 'fn'
VALIDATIONS = 'validations'
MODULE_TYPE_MAP = {
    'careplan': {
        FN: _new_careplan_module,
        VALIDATIONS: common_module_validations + [
            (lambda app: app.has_careplan_module,
             _('This application already has a Careplan module'))
        ]
    },
    'advanced': {
        FN: _new_advanced_module,
        VALIDATIONS: common_module_validations
    },
    'report': {
        FN: _new_report_module,
        VALIDATIONS: common_module_validations
    },
    'shadow': {
        FN: _new_shadow_module,
        VALIDATIONS: common_module_validations
    },
}
