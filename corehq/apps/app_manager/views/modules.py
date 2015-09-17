from collections import OrderedDict, namedtuple
from django.utils.translation import gettext_lazy
from corehq.apps.app_manager.const import USERCASE_TYPE, CAREPLAN_GOAL, CAREPLAN_TASK
from corehq.apps.app_manager.models import CareplanModule, AdvancedModule, \
    ReportModule
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.util import is_usercase_in_use, get_per_type_defaults, \
    ParentCasePropertyBuilder, prefix_usercase_properties, \
    commtrack_ledger_sections
from corehq.apps.fixtures.models import FixtureDataType
from corehq import ReportConfiguration
from corehq import toggles


def get_module_template(module):
    if isinstance(module, CareplanModule):
        return "app_manager/module_view_careplan.html"
    elif isinstance(module, AdvancedModule):
        return "app_manager/module_view_advanced.html"
    elif isinstance(module, ReportModule):
        return 'app_manager/module_view_report.html'
    else:
        return "app_manager/module_view.html"


def get_module_view_context(app, module):
    if isinstance(module, CareplanModule):
        return _get_careplan_module_view_context(app, module)
    elif isinstance(module, AdvancedModule):
        return _get_advanced_module_view_context(app, module)
    elif isinstance(module, ReportModule):
        return _get_report_module_context(app, module)
    else:
        return _get_basic_module_view_context(app, module)


def _get_careplan_module_view_context(app, module):
    case_property_builder = _setup_case_property_builder(app)
    subcase_types = list(app.get_subcase_types(module.case_type))
    return {
        'parent_modules': get_parent_modules(app, module,
                                             case_property_builder,
                                             CAREPLAN_GOAL),
        'fixtures': _get_fixture_types(app.domain),
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


def _get_advanced_module_view_context(app, module):
    case_property_builder = _setup_case_property_builder(app)
    case_type = module.case_type
    form_options = _case_list_form_options(app, module, case_type)
    return {
        'fixtures': _get_fixture_types(app.domain),
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
        'schedule_phases': [{
                                'id': schedule.id,
                                'anchor': schedule.anchor,
                                'forms': [form.schedule_form_id for form in
                                          schedule.get_forms()],
                            } for schedule in module.get_schedule_phases()],
    }


def _get_basic_module_view_context(app, module):
    case_property_builder = _setup_case_property_builder(app)
    fixture_columns = [
        field.field_name
        for fixture in FixtureDataType.by_domain(app.domain)
        for field in fixture.fields
    ]
    case_type = module.case_type
    form_options = _case_list_form_options(app, module, case_type)
    # don't allow this for modules with parent selection until this mobile bug is fixed:
    # http://manage.dimagi.com/default.asp?178635
    allow_case_list_form = _case_list_form_not_allowed_reason(
        module,
        AllowWithReason(not module.parent_select.active,
                        AllowWithReason.PARENT_SELECT_ACTIVE)
    )
    return {
        'parent_modules': get_parent_modules(app, module,
                                             case_property_builder, case_type),
        'fixtures': _get_fixture_types(app.domain),
        'fixture_columns': fixture_columns,
        'details': _get_module_details_context(app, module,
                                               case_property_builder,
                                               case_type),
        'case_list_form_options': form_options,
        'case_list_form_not_allowed_reason': allow_case_list_form,
        'valid_parent_modules': [parent_module
                                 for parent_module in app.modules
                                 if
                                 not getattr(parent_module, 'root_module_id',
                                             None) and
                                 not parent_module == module],
        'child_module_enabled': toggles.BASIC_CHILD_MODULE.enabled(app.domain)
    }


def _get_report_module_context(app, module):
    def _report_to_config(report):
        return {
            'report_id': report._id,
            'title': report.title,
            'charts': [chart for chart in report.charts if
                       chart.type == 'multibar'],
            'filter_structure': report.filters,
        }

    all_reports = ReportConfiguration.by_domain(app.domain)
    all_report_ids = set([r._id for r in all_reports])
    invalid_report_references = filter(
        lambda r: r.report_id not in all_report_ids, module.report_configs)
    warnings = []
    if invalid_report_references:
        module.report_configs = filter(lambda r: r.report_id in all_report_ids,
                                       module.report_configs)
        warnings.append(
            gettext_lazy(
                'Your app contains references to reports that are deleted. These will be removed on save.')
        )
    return {
        'all_reports': [_report_to_config(r) for r in all_reports],
        'current_reports': [r.to_json() for r in module.report_configs],
        'invalid_report_references': invalid_report_references,
        'warnings': warnings,
    }


def _get_fixture_types(domain):
    # TODO: Don't hit the DB here and when getting fixture columns
    return [f.tag for f in FixtureDataType.by_domain(domain)]


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


def get_parent_modules(app, module, case_property_builder, case_type_):
        parent_types = case_property_builder.get_parent_types(case_type_)
        modules = app.modules
        parent_module_ids = [mod.unique_id for mod in modules
                             if mod.case_type in parent_types]
        return [{
            'unique_id': mod.unique_id,
            'name': mod.name,
            'is_parent': mod.unique_id in parent_module_ids,
        } for mod in app.modules if mod.case_type != case_type_ and mod.unique_id != module.unique_id]


def _case_list_form_options(app, module, case_type_):
    options = OrderedDict()
    forms = [
        form
        for mod in app.get_modules() if module.unique_id != mod.unique_id
        for form in mod.get_forms() if form.is_registration_form(case_type_)
    ]
    options['disabled'] = gettext_lazy("Don't Show")
    options.update({f.unique_id: trans(f.name, app.langs) for f in forms})

    return options


def _get_module_details_context(app, module, case_property_builder, case_type_):
    subcase_types = list(app.get_subcase_types(module.case_type))
    item = {
        'label': gettext_lazy('Case List'),
        'detail_label': gettext_lazy('Case Detail'),
        'type': 'case',
        'model': 'case',
        'sort_elements': module.case_details.short.sort_elements,
        'short': module.case_details.short,
        'long': module.case_details.long,
        'subcase_types': subcase_types,
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
        "case_type": None, "put_in_root": None, "display_separately": None,
        "name": None, "case_label": None, "referral_label": None,
        'media_image': None, 'media_audio': None, 'has_schedule': None,
        "case_list": ('case_list-show', 'case_list-label'),
        "task_list": ('task_list-show', 'task_list-label'),
        "case_list_form_id": None,
        "case_list_form_label": None,
        "case_list_form_media_image": None,
        "case_list_form_media_audio": None,
        'case_list-menu_item_media_image': None,
        'case_list-menu_item_media_audio': None,
        "parent_module": None,
        "root_module_id": None,
        "module_filter": None,
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
        if is_valid_case_type(case_type):
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
        elif case_type == USERCASE_TYPE:
            return HttpResponseBadRequest('"{}" is a reserved case type'.format(USERCASE_TYPE))
        else:
            return HttpResponseBadRequest("case type is improperly formatted")
    if should_edit("put_in_root"):
        module["put_in_root"] = json.loads(request.POST.get("put_in_root"))
    if should_edit("display_separately"):
        module["display_separately"] = json.loads(request.POST.get("display_separately"))
    if should_edit("parent_module"):
        parent_module = request.POST.get("parent_module")
        module.parent_select.module_id = parent_module

    if (feature_previews.MODULE_FILTER.enabled(app.domain) and
            app.enable_module_filtering and
            should_edit('module_filter')):
        module['module_filter'] = request.POST.get('module_filter')

    if should_edit('case_list_form_id'):
        module.case_list_form.form_id = request.POST.get('case_list_form_id')
    if should_edit('case_list_form_label'):
        module.case_list_form.label[lang] = request.POST.get('case_list_form_label')
    if should_edit('case_list_form_media_image'):
        new_path = _process_media_attribute(
            'case_list_form_media_image',
            resp,
            request.POST.get('case_list_form_media_image')
        )
        module.case_list_form.set_icon(lang, new_path)

    if should_edit('case_list_form_media_audio'):
        new_path = _process_media_attribute(
            'case_list_form_media_audio',
            resp,
            request.POST.get('case_list_form_media_audio')
        )
        module.case_list_form.set_audio(lang, new_path)

    if should_edit('case_list-menu_item_media_image'):
        val = _process_media_attribute(
            'case_list-menu_item_media_image',
            resp,
            request.POST.get('case_list-menu_item_media_image')
        )
        module.case_list.set_icon(lang, val)
    if should_edit('case_list-menu_item_media_audio'):
        val = _process_media_attribute(
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

    _handle_media_edits(request, module, should_edit, resp, lang)

    app.save(resp)
    resp['case_list-show'] = module.requires_case_details()
    return HttpResponse(json.dumps(resp))

