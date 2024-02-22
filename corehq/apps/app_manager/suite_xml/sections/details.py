"""
DetailContributor
-----------------

Details represent the configuration for case lists and case details. The
reuse of the word "Detail" here is unfortunate. Details **can** be used
for other purposes, such as the ``referral_detail``, but 99% of the
time they're used for case list/detail.

The case list is the "short" detail and the case detail is the "long"
detail. A handful of configurations are only supported for one of
these, e.g., actions only get added to the short detail.

The detail element can be nested. HQ never nests short details, but it
nests long details to produce tabbed case details. Each tab has its own
``<detail>`` element.

The bulk of detail configuration is in the display properties,
called "fields" and sometimes "columns" in the code. Each field has a
good deal of configuration, and the code transforms them into named
tuples while processing them. Each field has a format, one of about a
dozen options. Formats are typically either UI-based, such as
formatting a phone number to display as a link, or calculation-based,
such as configuring a property to display differently when it's "late",
i.e., is too far past some reference date.

Most fields map to a particular case property, with the exception of
calculated properties. These calculated properties are identified only
by number. A typical field might be called ``case_dob_1`` in the suite,
indicating both its position and its case property, but a calculation
would be called ``case_calculated_property_1``.

"""
from collections import defaultdict, namedtuple

from eulxml.xmlmap.core import load_xmlobject_from_string
from memoized import memoized

from corehq import toggles
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import RETURN_TO
from corehq.apps.app_manager.exceptions import SuiteValidationError
from corehq.apps.app_manager.id_strings import callout_header_locale
from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_LEDGER
from corehq.apps.app_manager.suite_xml.contributors import SectionContributor
from corehq.apps.app_manager.suite_xml.features.case_tiles import CaseTileHelper
from corehq.apps.app_manager.suite_xml.features.scheduler import (
    schedule_detail_variables,
)
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.app_manager.suite_xml.xml_models import (
    Action,
    Detail,
    DetailVariable,
    Display,
    Extra,
    Field,
    Header,
    Id,
    Locale,
    LocalizedAction,
    Lookup,
    PushFrame,
    Response,
    Stack,
    StackDatum,
    Style,
    Template,
    Text,
    TextXPath,
    XPathVariable,
)
from corehq.apps.app_manager.util import (
    create_temp_sort_column,
    get_sort_and_sort_only_columns,
    module_loads_registry_case,
    module_offers_search,
    module_uses_inline_search,
)
from corehq.apps.app_manager.xpath import CaseXPath, CaseTypeXpath, XPath, interpolate_xpath, session_var
from corehq.util.timer import time_method

AUTO_LAUNCH_EXPRESSIONS = {
    "single-select": "$next_input = '' or count(instance('casedb')/casedb/case[@case_id=$next_input]) = 0",
    "multi-select": ("count(instance('next_input')/results/value) = 0"
                     " or count(instance('next_input')/results/value"
                     "[count(instance('casedb')/casedb/case[@case_id = current()/.]) = 0]) > 0")
}


class DetailContributor(SectionContributor):
    section_name = 'details'

    @time_method()
    def get_section_elements(self):
        if self.app.use_custom_suite:
            return []

        elements = []
        for module in self.modules:
            for detail_type, detail, enabled in module.get_details():
                if not enabled:
                    continue

                if detail.custom_xml:
                    elements.append(self._get_custom_xml_detail(module, detail, detail_type))
                else:
                    if detail.sort_nodeset_columns_for_detail():
                        # list of DetailColumnInfo named tuples
                        detail_column_infos = get_detail_column_infos_for_tabs_with_sorting(detail)
                    else:
                        detail_column_infos = get_detail_column_infos(
                            detail_type,
                            detail,
                            include_sort=detail_type.endswith('short'),
                        )  # list of DetailColumnInfo named tuples
                    if detail_column_infos:
                        detail_id = id_strings.detail(module, detail_type)
                        locale_id = id_strings.detail_title_locale(detail_type)
                        title = Text(locale_id=locale_id) if locale_id else Text()
                        d = self.build_detail(
                            module,
                            detail_type,
                            detail,
                            detail_column_infos,
                            title,
                            tabs=list(detail.get_tabs()),
                            id=detail_id,
                            print_template=detail.print_template['path'] if detail.print_template else None,
                        )
                        if d:
                            elements.append(d)

                    # add the persist case context if needed and if
                    # case tiles are present and have their own persistent block
                    if (detail.persist_case_context
                            and not (detail.case_tile_template and detail.persist_tile_on_forms)):
                        d = self._get_persistent_case_context_detail(module, detail.persistent_case_context_xml)
                        elements.append(d)

            if module.fixture_select.active:
                d = self._get_fixture_detail(module)
                elements.append(d)

        if toggles.MOBILE_UCR.enabled(self.app.domain):
            if any([getattr(m, 'report_context_tile', False) for m in self.app.get_modules()]):
                elements.append(self._get_report_context_tile_detail())

        return elements

    def build_detail(self, module, detail_type, detail, detail_column_infos, title, tabs=None, id=None,
                     nodeset=None, print_template=None, start=0, end=None, relevant=None):
        """
        Recursively builds the Detail object.
        (Details can contain other details for each of their tabs)
        """
        from corehq.apps.app_manager.detail_screen import get_column_generator
        d = Detail(id=id, title=title, nodeset=nodeset, print_template=print_template, relevant=relevant)
        if (detail_type == 'case_short' or detail_type == 'search_short') \
                and hasattr(module, 'lazy_load_case_list_fields') and module.lazy_load_case_list_fields:
            d.lazy_loading = module.lazy_load_case_list_fields

        self._add_custom_variables(detail, d)
        if tabs:
            tab_spans = detail.get_tab_spans()
            for tab in tabs:
                # relevant should be set to None even in case its ''
                tab_relevant = None
                if tab.relevant:
                    tab_relevant = tab.relevant

                sub_detail = self.build_detail(
                    module,
                    detail_type,
                    detail,
                    detail_column_infos,
                    Text(locale_id=id_strings.detail_tab_title_locale(
                        module, detail_type, tab
                    )),
                    nodeset=self._get_detail_tab_nodeset(module, detail, tab),
                    start=tab_spans[tab.id][0],
                    end=tab_spans[tab.id][1],
                    relevant=tab_relevant,
                )
                if sub_detail:
                    d.details.append(sub_detail)
            if len(d.details):
                helper = EntriesHelper(self.app)
                datums = helper.get_datum_meta_module(module)
                d.variables.extend([
                    DetailVariable(name=datum.id, function=datum.datum.value)
                    for datum in datums
                    # FixtureSelect isn't supported under variables
                    # More context here: https://github.com/dimagi/commcare-hq/pull/33769#discussion_r1410315708
                    if datum.action != 'fixture_select'
                ])
                return d
            else:
                return None

        # Base case (has no tabs)
        else:
            # Add lookup
            if detail.lookup_enabled and detail.lookup_action:
                d.lookup = self._get_lookup_element(detail, module)

            # Add variables
            variables = list(
                schedule_detail_variables(module, detail, detail_column_infos)
            )
            if variables:
                d.variables.extend(variables)
            if end is None:
                end = len(detail_column_infos)

            # Add fields
            if detail.case_tile_template:
                helper = CaseTileHelper(
                    self.app,
                    module,
                    detail,
                    id,
                    detail_type,
                    self.build_profile_id,
                    detail_column_infos,
                    self.entries_helper,
                )
                d = helper.build_case_tile_detail(d, start, end)
            else:
                for column_info in detail_column_infos[start:end]:
                    # column_info is an instance of DetailColumnInfo named tuple.
                    fields = get_column_generator(
                        self.app, module, detail, parent_tab_nodeset=nodeset,
                        detail_type=detail_type, entries_helper=self.entries_helper,
                        *column_info
                    ).fields
                    for field in fields:
                        d.fields.append(field)

                # Add actions
                if detail_type.endswith('short') and not module.put_in_root:
                    if module.case_list_form.form_id:
                        DetailContributor.add_register_action(
                            self.app, module, d.actions, self.build_profile_id, self.entries_helper)

            # Add actions
            if detail_type.endswith('short') and not module.put_in_root:
                if module_offers_search(module) and not module_uses_inline_search(module):
                    if (case_search_action := DetailContributor.get_case_search_action(
                        module,
                        self.build_profile_id,
                        id
                    )) is not None:
                        d.actions.append(case_search_action)
            # Add select text
            self.add_select_text_to_detail(d, self.app, detail_type, module)
            self.add_no_items_text_to_detail(d, self.app, detail_type, module)

            try:
                if not self.app.enable_multi_sort:
                    d.fields[0].sort = 'default'
            except IndexError:
                pass
            else:
                # only yield the Detail if it has Fields
                return d

    def _add_custom_variables(self, detail, d):
        custom_variables_dict = detail.custom_variables_dict
        if custom_variables_dict:
            d.variables.extend(
                DetailVariable(name=name, function=function) for name, function in custom_variables_dict.items()
            )

    def _get_detail_tab_nodeset(self, module, detail, tab):
        if not tab.has_nodeset:
            return None

        if tab.nodeset:
            return tab.nodeset

        if tab.nodeset_case_type:
            nodeset = CaseTypeXpath(tab.nodeset_case_type)
            nodeset = nodeset.case(instance_name=detail.get_instance_name(module))
            nodeset = nodeset.select(CaseXPath().parent_id(),
                                     CaseXPath("current()").property("@case_id"))
            nodeset = nodeset.select("@status", "open")
            if tab.nodeset_filter:
                nodeset = nodeset.select_raw(interpolate_xpath(tab.nodeset_filter))
            return nodeset

        return None

    def _get_lookup_element(self, detail, module):
        if detail.lookup_display_results:
            field = Field(
                header=Header(
                    width=None if detail.lookup_field_header else 0,
                    text=Text(locale_id=callout_header_locale(module)) if detail.lookup_field_header else None,
                ),
                template=Template(
                    text=Text(xpath_function=detail.lookup_field_template)
                ),
            )
        else:
            field = None
        return Lookup(
            name=detail.lookup_name or None,
            auto_launch=detail.lookup_autolaunch or False,
            action=detail.lookup_action,
            image=detail.lookup_image or None,
            extras=[Extra(**e) for e in detail.lookup_extras],
            responses=[Response(**r) for r in detail.lookup_responses],
            field=field,
        )

    @staticmethod
    def add_register_action(app, module, actions, build_profile_id, entries_helper):
        from corehq.apps.app_manager.views.modules import get_parent_select_followup_forms
        form = app.get_form(module.case_list_form.form_id)
        if toggles.FOLLOWUP_FORMS_AS_CASE_LIST_FORM.enabled(app.domain):
            valid_forms = [f.unique_id for f in get_parent_select_followup_forms(app, module)]
        else:
            valid_forms = []
        if form.is_registration_form(module.case_type) or form.unique_id in valid_forms:
            actions.append(DetailContributor.get_case_list_form_action(
                module, app, build_profile_id, entries_helper))

    @staticmethod
    def get_case_list_form_action(module, app, build_profile_id, entries_helper):
        """
        Returns registration/followup form action
        """
        form = app.get_form(module.case_list_form.form_id)

        if app.enable_localized_menu_media:
            case_list_form = module.case_list_form
            action = LocalizedAction(
                menu_locale_id=id_strings.case_list_form_locale(module),
                media_image=case_list_form.uses_image(build_profile_id=build_profile_id),
                media_audio=case_list_form.uses_audio(build_profile_id=build_profile_id),
                image_locale_id=id_strings.case_list_form_icon_locale(module),
                audio_locale_id=id_strings.case_list_form_audio_locale(module),
                stack=Stack(),
                for_action_menu=True,
            )
        else:
            action = Action(
                display=Display(
                    text=Text(locale_id=id_strings.case_list_form_locale(module)),
                    media_image=module.case_list_form.default_media_image,
                    media_audio=module.case_list_form.default_media_audio,
                ),
                stack=Stack(),
            )

        action_relevant = module.case_list_form.relevancy_expression
        if toggles.FOLLOWUP_FORMS_AS_CASE_LIST_FORM.enabled(app.domain) and action_relevant:
            action.relevant = action_relevant

        frame = PushFrame()
        frame.add_command(XPath.string(id_strings.form_command(form)))
        for datum in DetailContributor.get_datums_for_action(entries_helper, module, form):
            frame.add_datum(datum)

        frame.add_datum(StackDatum(id=RETURN_TO, value=XPath.string(id_strings.menu_id(module))))
        action.stack.add_frame(frame)
        return action

    @staticmethod
    def get_datums_for_action(entries_helper, source_module, target_form):
        target_form_dm = entries_helper.get_datums_meta_for_form_generic(target_form)
        source_form_dm = []
        if len(source_module.forms):
            source_form_dm = entries_helper.get_datums_meta_for_form_generic(source_module.get_form(0))
        for target_meta in target_form_dm:
            if target_meta.requires_selection:
                # This is true for registration forms where the case being created is a subcase
                try:
                    [source_dm] = [
                        source_meta for source_meta in source_form_dm
                        if source_meta.case_type == target_meta.case_type
                    ]
                except ValueError:
                    pass
                else:
                    yield StackDatum(
                        id=target_meta.id,
                        value=session_var(source_dm.id))
            else:
                s_datum = target_meta.datum
                yield StackDatum(id=s_datum.id, value=s_datum.function)

    @staticmethod
    def get_case_search_action(module, build_profile_id, detail_id):
        in_search = module_loads_registry_case(module) or "search" in detail_id

        # don't add search again action in split screen
        if in_search and toggles.SPLIT_SCREEN_CASE_SEARCH.enabled(module.get_app().domain):
            return None

        action_kwargs = DetailContributor._get_action_kwargs(module, in_search)
        if in_search:
            search_label = module.search_config.search_again_label
        else:
            search_label = module.search_config.search_label

        if module.get_app().enable_localized_menu_media:
            action = LocalizedAction(
                menu_locale_id=(
                    id_strings.case_search_again_locale(module) if in_search
                    else id_strings.case_search_locale(module)
                ),
                media_image=search_label.uses_image(build_profile_id=build_profile_id),
                media_audio=search_label.uses_audio(build_profile_id=build_profile_id),
                image_locale_id=(
                    id_strings.case_search_again_icon_locale(module) if in_search
                    else id_strings.case_search_icon_locale(module)
                ),
                audio_locale_id=(
                    id_strings.case_search_again_audio_locale(module) if in_search
                    else id_strings.case_search_audio_locale(module)
                ),
                stack=Stack(),
                for_action_menu=True,
                **action_kwargs,
            )
        else:
            action = Action(
                display=Display(
                    text=Text(locale_id=(
                        id_strings.case_search_again_locale(module) if in_search
                        else id_strings.case_search_locale(module)
                    )),
                    media_image=search_label.default_media_image,
                    media_audio=search_label.default_media_audio
                ),
                stack=Stack(),
                **action_kwargs
            )
        frame = PushFrame()
        frame.add_mark()
        frame.add_command(XPath.string(id_strings.search_command(module)))
        action.stack.add_frame(frame)
        return action

    @staticmethod
    def _get_action_kwargs(module, in_search):
        action_kwargs = {
            'auto_launch': DetailContributor._get_auto_launch_expression(module, in_search),
            'redo_last': in_search,
        }
        relevant = DetailContributor._get_relevant_expression(module, in_search)
        if relevant:
            action_kwargs["relevant"] = relevant
        return action_kwargs

    @staticmethod
    def _get_relevant_expression(module, in_search):
        if not in_search and module.search_config.search_button_display_condition:
            return XPath(module.search_config.search_button_display_condition)

    @staticmethod
    def _get_auto_launch_expression(module, in_search):
        allow_auto_launch = toggles.USH_CASE_CLAIM_UPDATES.enabled(module.get_app().domain) and not in_search
        auto_launch_expression = "false()"
        if allow_auto_launch and module.search_config.auto_launch:
            if module.is_multi_select():
                auto_launch_expression = XPath(AUTO_LAUNCH_EXPRESSIONS['multi-select'])
            else:
                auto_launch_expression = XPath(AUTO_LAUNCH_EXPRESSIONS['single-select'])
        return auto_launch_expression

    def _get_custom_xml_detail(self, module, detail, detail_type):
        d = load_xmlobject_from_string(
            detail.custom_xml,
            xmlclass=Detail
        )

        expected = id_strings.detail(module, detail_type)
        if not id_strings.is_custom_app_string(d.id) and d.id != expected:
            raise SuiteValidationError(
                "Menu {}, \"{}\", uses custom case list xml. The "
                "specified detail ID is '{}', expected '{}'"
                .format(module.id, module.default_name(), d.id, expected)
            )

        return d

    @staticmethod
    def _get_persistent_case_context_detail(module, xml):
        return Detail(
            id=id_strings.persistent_case_context_detail(module),
            title=Text(),
            fields=[Field(
                style=Style(
                    horz_align="center",
                    font_size="large",
                    grid_height=1,
                    grid_width=12,
                    grid_x=0,
                    grid_y=0,
                    show_border=False,
                    show_shading=False,
                ),
                header=Header(text=Text()),
                template=Template(text=Text(xpath_function=xml)),
            )]
        )

    @staticmethod
    def _get_report_context_tile_detail():
        from corehq.apps.app_manager.suite_xml.features.mobile_ucr import (
            MOBILE_UCR_TILE_DETAIL_ID,
        )
        return Detail(
            id=MOBILE_UCR_TILE_DETAIL_ID,
            title=Text(),
            fields=[Field(
                style=Style(
                    horz_align="left",
                    font_size="small",
                    grid_height=1,
                    grid_width=12,
                    grid_x=0,
                    grid_y=0,
                    show_border=False,
                    show_shading=False,
                ),
                header=Header(text=Text()),
                template=Template(text=Text(xpath=TextXPath(
                    function="concat($message, ' ', format-date(date(instance('commcare-reports:index')/report_index/reports/@last_update), '%e/%n/%Y'))",  # noqa: E501
                    variables=[XPathVariable(name='message', locale_id=id_strings.reports_last_updated_on())],
                ))),
            )]
        )

    @staticmethod
    def _get_fixture_detail(module):
        d = Detail(
            id=id_strings.fixture_detail(module),
            title=Text(),
        )
        xpath = TextXPath(function=module.fixture_select.display_column)
        if module.fixture_select.localize:
            template_text = Text(locale=Locale(child_id=Id(xpath=xpath)))
        else:
            template_text = Text(
                xpath_function=module.fixture_select.display_column)
        fields = [Field(header=Header(text=Text()),
                        template=Template(text=template_text),
                        sort_node='')]
        d.fields = fields
        return d

    @staticmethod
    def add_no_items_text_to_detail(detail, app, detail_type, module):
        if detail_type.endswith('short') and app.supports_empty_case_list_text:
            detail.no_items_text = Text(locale_id=id_strings.no_items_text_detail(module))

    @staticmethod
    def add_select_text_to_detail(detail, app, detail_type, module):
        if detail_type.endswith('short') and app.supports_select_text:
            detail.select_text = Text(locale_id=id_strings.select_text_detail(module))


class DetailsHelper(object):

    def __init__(self, app, modules=None):
        self.app = app
        self._modules = modules

    @property
    @memoized
    def modules(self):
        return self._modules or list(self.app.get_modules())

    @property
    @memoized
    def active_details(self):
        return {
            id_strings.detail(module, detail_type)
            for module in self.modules for detail_type, detail, enabled in module.get_details()
            if enabled and detail.columns
        }

    def get_detail_id_safe(self, module, detail_type):
        detail_id = id_strings.detail(
            module=module,
            detail_type=detail_type,
        )
        return detail_id if detail_id in self.active_details else None


def get_nodeset_sort_elements(detail):
    from corehq.apps.app_manager.models import SortElement
    sort_elements = defaultdict(list)
    tab_spans = detail.get_tab_spans()
    for tab in detail.get_tabs():
        if tab.has_nodeset:
            tab_span = tab_spans[tab.id]
            for column in detail.columns[tab_span[0]:tab_span[1]]:
                if column.invisible:
                    sort_elements[tab.id].append(SortElement(
                        field=column.field,
                        type='string',
                        direction='ascending'
                    ))
    return sort_elements


def get_default_sort_elements(detail):
    from corehq.apps.app_manager.models import SortElement

    if not detail.columns:
        return []

    def get_sort_params(column):
        if column.field_type == FIELD_TYPE_LEDGER:
            return dict(type='int', direction='descending')
        else:
            return dict(type='string', direction='ascending')

    col_0 = detail.get_column(0)
    sort_elements = [SortElement(
        field=col_0.field,
        **get_sort_params(col_0)
    )]

    for column in detail.columns[1:]:
        if column.field_type == FIELD_TYPE_LEDGER:
            sort_elements.append(SortElement(
                field=column.field,
                **get_sort_params(column)
            ))

    return sort_elements


# This is not intended to be a widely used format
# just a packaging of column info into a form most convenient for rendering
# It has the following properties:
#   column_info.column: an instance of app_manager.models.DetailColumn
#   column_info.sort_element: an instance of app_manager.models.SortElement
#   column_info.order: an integer
DetailColumnInfo = namedtuple('DetailColumnInfo', 'column sort_element order')


def get_detail_column_infos(detail_type, detail, include_sort):
    detail_columns = list(detail.get_columns())  # evaluate generator
    if not include_sort:
        return [DetailColumnInfo(column, None, None) for column in detail_columns]

    if detail.sort_elements:
        sort_elements = detail.sort_elements
    else:
        sort_elements = get_default_sort_elements(detail)

    sort_only, sort_columns = get_sort_and_sort_only_columns(detail_columns, sort_elements)

    columns = []
    for column in detail_columns:
        sort_element, order = sort_columns.pop(column.field, (None, None))
        if getattr(sort_element, 'type', None) == 'index' and "search" in detail_type:
            columns.append(DetailColumnInfo(column, None, None))
        else:
            columns.append(DetailColumnInfo(column, sort_element, order))

    for field, sort_element, order in sort_only:
        column = create_temp_sort_column(sort_element, order)
        if getattr(sort_element, 'type', None) == 'index' and "search" in detail_type:
            columns.append(DetailColumnInfo(column, None, None))
        else:
            columns.append(DetailColumnInfo(column, sort_element, order))
    return columns


def get_detail_column_infos_for_tabs_with_sorting(detail):
    """This serves the same purpose as `get_detail_column_infos` except
    that it only applies to 'long' details that have tabs with nodesets and sorting
    configured."""
    sort_elements = get_nodeset_sort_elements(detail)

    columns = []
    tab_spans = detail.get_tab_spans()
    detail_columns = list(detail.get_columns())  # do this to ensure we get the indexed values
    for tab in detail.get_tabs():
        tab_span = tab_spans[tab.id]
        tab_columns = detail_columns[tab_span[0]:tab_span[1]]
        if tab.has_nodeset and sort_elements[tab.id]:
            tab_sorts = sort_elements[tab.id]
            _, sort_columns = get_sort_and_sort_only_columns(tab_columns, tab_sorts)
            for column in tab_columns:
                if column.invisible:
                    sort_element, order = sort_columns.pop(column.field, (None, None))
                    columns.append(DetailColumnInfo(column, sort_element, order))
                else:
                    columns.append(DetailColumnInfo(column, None, None))
        else:
            columns.extend([
                DetailColumnInfo(column, None, None)
                for column in tab_columns
            ])

    return columns
