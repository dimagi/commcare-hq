import os
from collections import defaultdict, namedtuple
from xml.sax.saxutils import escape

from eulxml.xmlmap.core import load_xmlobject_from_string
from lxml import etree
from memoized import memoized

from corehq import toggles
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import RETURN_TO
from corehq.apps.app_manager.exceptions import SuiteError, SuiteValidationError
from corehq.apps.app_manager.id_strings import callout_header_locale
from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_LEDGER
from corehq.apps.app_manager.suite_xml.contributors import SectionContributor
from corehq.apps.app_manager.suite_xml.features.scheduler import (
    schedule_detail_variables,
)
from corehq.apps.app_manager.suite_xml.post_process.instances import (
    get_all_instances_referenced_in_xpaths,
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
    Xpath,
    XpathVariable,
)
from corehq.apps.app_manager.util import (
    create_temp_sort_column,
    get_sort_and_sort_only_columns,
    module_offers_search,
)
from corehq.apps.app_manager.xpath import CaseXPath, CaseTypeXpath, XPath, session_var
from corehq.util.timer import time_method

AUTO_LAUNCH_EXPRESSION = "$next_input = '' or count(instance('casedb')/casedb/case[@case_id=$next_input]) = 0"


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
                        if detail.use_case_tiles:
                            helper = CaseTileHelper(self.app, module, detail,
                                                    detail_type, self.build_profile_id)
                            elements.append(helper.build_case_tile_detail())
                        else:
                            print_template_path = None
                            if detail.print_template:
                                print_template_path = detail.print_template['path']
                            locale_id = id_strings.detail_title_locale(detail_type)
                            title = Text(locale_id=locale_id) if locale_id else Text()
                            d = self.build_detail(
                                module,
                                detail_type,
                                detail,
                                detail_column_infos,
                                tabs=list(detail.get_tabs()),
                                id=id_strings.detail(module, detail_type),
                                title=title,
                                print_template=print_template_path,
                            )
                            if d:
                                elements.append(d)

                    # add the persist case context if needed and if
                    # case tiles are present and have their own persistent block
                    if (detail.persist_case_context and
                            not (detail.use_case_tiles and detail.persist_tile_on_forms)):
                        d = self._get_persistent_case_context_detail(module, detail.persistent_case_context_xml)
                        elements.append(d)

            if module.fixture_select.active:
                d = self._get_fixture_detail(module)
                elements.append(d)

        if toggles.MOBILE_UCR.enabled(self.app.domain):
            if any([getattr(m, 'report_context_tile', False) for m in self.app.get_modules()]):
                elements.append(self._get_report_context_tile_detail())

        return elements

    def build_detail(self, module, detail_type, detail, detail_column_infos, tabs=None, id=None,
                     title=None, nodeset=None, print_template=None, start=0, end=None, relevant=None):
        """
        Recursively builds the Detail object.
        (Details can contain other details for each of their tabs)
        """
        from corehq.apps.app_manager.detail_screen import get_column_generator
        d = Detail(id=id, title=title, nodeset=nodeset, print_template=print_template, relevant=relevant)
        self._add_custom_variables(detail, d)
        if tabs:
            tab_spans = detail.get_tab_spans()
            for tab in tabs:
                # relevant should be set to None even in case its ''
                tab_relevant = None
                if tab.relevant and toggles.DISPLAY_CONDITION_ON_TABS.enabled(module.get_app().domain):
                    tab_relevant = tab.relevant

                sub_detail = self.build_detail(
                    module,
                    detail_type,
                    detail,
                    detail_column_infos,
                    title=Text(locale_id=id_strings.detail_tab_title_locale(
                        module, detail_type, tab
                    )),
                    nodeset=self._get_detail_tab_nodeset(detail, tab),
                    start=tab_spans[tab.id][0],
                    end=tab_spans[tab.id][1],
                    relevant=tab_relevant,
                )
                if sub_detail:
                    d.details.append(sub_detail)
            if len(d.details):
                helper = EntriesHelper(self.app)
                datums = helper.get_datum_meta_module(module)
                d.variables.extend([DetailVariable(name=datum.datum.id, function=datum.datum.value) for datum in datums])
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

            # Add fields
            if end is None:
                end = len(detail_column_infos)
            for column_info in detail_column_infos[start:end]:
                # column_info is an instance of DetailColumnInfo named tuple. It has the following properties:
                #   column_info.column: an instance of app_manager.models.DetailColumn
                #   column_info.sort_element: an instance of app_manager.models.SortElement
                #   column_info.order: an integer
                fields = get_column_generator(
                    self.app, module, detail, parent_tab_nodeset=nodeset,
                    detail_type=detail_type, *column_info
                ).fields
                for field in fields:
                    d.fields.append(field)

            # Add actions
            if detail_type.endswith('short') and not module.put_in_root:
                if module.case_list_form.form_id:
                    from corehq.apps.app_manager.views.modules import get_parent_select_followup_forms
                    form = self.app.get_form(module.case_list_form.form_id)
                    if toggles.FOLLOWUP_FORMS_AS_CASE_LIST_FORM.enabled(self.app.domain):
                        valid_forms = [f.unique_id for f in get_parent_select_followup_forms(self.app, module)]
                    else:
                        valid_forms = []
                    if form.is_registration_form(module.case_type) or form.unique_id in valid_forms:
                        d.actions.append(self._get_case_list_form_action(module))

                if module_offers_search(module):
                    d.actions.append(self._get_case_search_action(module, in_search="search" in id))

            try:
                if not self.app.enable_multi_sort:
                    d.fields[0].sort = 'default'
            except IndexError:
                pass
            else:
                # only yield the Detail if it has Fields
                return d

    def _add_custom_variables(self, detail, d):
        custom_variables = detail.custom_variables
        if custom_variables:
            custom_variable_elements = [
                variable for variable in
                etree.fromstring("<variables>{}</variables>".format(custom_variables))
            ]
            d.variables.extend([
                load_xmlobject_from_string(etree.tostring(e, encoding='utf-8'), xmlclass=DetailVariable)
                for e in custom_variable_elements
            ])

    def _get_detail_tab_nodeset(self, detail, tab):
        if not tab.has_nodeset:
            return None

        if tab.nodeset:
            return tab.nodeset

        if tab.nodeset_case_type:
            nodeset = CaseTypeXpath(tab.nodeset_case_type)
            nodeset = nodeset.case(instance_name=detail.instance_name)
            nodeset = nodeset.select(CaseXPath().parent_id(),
                                     CaseXPath("current()").property("@case_id"))
            nodeset = nodeset.select("@status", "open")
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

    def _get_case_list_form_action(self, module):
        """
        Returns registration/followup form action
        """
        form = self.app.get_form(module.case_list_form.form_id)

        if self.app.enable_localized_menu_media:
            case_list_form = module.case_list_form
            action = LocalizedAction(
                menu_locale_id=id_strings.case_list_form_locale(module),
                media_image=case_list_form.uses_image(build_profile_id=self.build_profile_id),
                media_audio=case_list_form.uses_audio(build_profile_id=self.build_profile_id),
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
        if toggles.FOLLOWUP_FORMS_AS_CASE_LIST_FORM.enabled(self.app.domain) and action_relevant:
            action.relevant = action_relevant

        frame = PushFrame()
        frame.add_command(XPath.string(id_strings.form_command(form)))

        target_form_dm = self.entries_helper.get_datums_meta_for_form_generic(form)
        source_form_dm = []
        if len(module.forms):
            source_form_dm = self.entries_helper.get_datums_meta_for_form_generic(module.get_form(0))
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
                    frame.add_datum(StackDatum(
                        id=target_meta.datum.id,
                        value=session_var(source_dm.datum.id))
                    )
            else:
                s_datum = target_meta.datum
                frame.add_datum(StackDatum(id=s_datum.id, value=s_datum.function))

        frame.add_datum(StackDatum(id=RETURN_TO, value=XPath.string(id_strings.menu_id(module))))
        action.stack.add_frame(frame)
        return action

    def _get_case_search_action(self, module, in_search=False):
        action_kwargs = DetailContributor._get_action_kwargs(module, in_search)
        if in_search:
            search_label = module.search_config.search_again_label
        else:
            search_label = module.search_config.search_label

        if self.app.enable_localized_menu_media:
            action = LocalizedAction(
                menu_locale_id=(
                    id_strings.case_search_again_locale(module) if in_search
                    else id_strings.case_search_locale(module)
                ),
                media_image=search_label.uses_image(build_profile_id=self.build_profile_id),
                media_audio=search_label.uses_audio(build_profile_id=self.build_profile_id),
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
            auto_launch_expression = XPath(AUTO_LAUNCH_EXPRESSION)
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
                ),
                header=Header(text=Text()),
                template=Template(text=Text(xpath=Xpath(
                    function="concat($message, ' ', format-date(date(instance('commcare-reports:index')/report_index/reports/@last_update), '%e/%n/%Y'))",
                    variables=[XpathVariable(name='message', locale_id=id_strings.reports_last_updated_on())],
                ))),
            )]
        )

    @staticmethod
    def _get_fixture_detail(module):
        d = Detail(
            id=id_strings.fixture_detail(module),
            title=Text(),
        )
        xpath = Xpath(function=module.fixture_select.display_column)
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
DetailColumnInfo = namedtuple('DetailColumnInfo', 'column sort_element order')


def get_detail_column_infos(detail_type, detail, include_sort):
    if not include_sort:
        return [DetailColumnInfo(column, None, None) for column in detail.get_columns()]

    if detail.sort_elements:
        sort_elements = detail.sort_elements
    else:
        sort_elements = get_default_sort_elements(detail)

    sort_only, sort_columns = get_sort_and_sort_only_columns(detail.get_columns(), sort_elements)

    columns = []
    for column in detail.get_columns():
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
    that it only applies to 'short' details that have tabs with nodesets and sorting
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


def get_instances_for_module(app, module, detail_section_elements):
    """
    This method is used by CloudCare when filtering cases.
    """
    modules = list(app.get_modules())
    helper = DetailsHelper(app, modules)
    details = detail_section_elements
    detail_mapping = {detail.id: detail for detail in details}
    details_by_id = detail_mapping
    detail_ids = [helper.get_detail_id_safe(module, detail_type)
                  for detail_type, detail, enabled in module.get_details()
                  if enabled]
    detail_ids = [_f for _f in detail_ids if _f]
    xpaths = set()

    for detail_id in detail_ids:
        xpaths.update(details_by_id[detail_id].get_all_xpaths())

    instances, _ = get_all_instances_referenced_in_xpaths(app, xpaths)
    return instances


class CaseTileHelper(object):
    tile_fields = ["header", "top_left", "sex", "bottom_left", "date"]

    def __init__(self, app, module, detail, detail_type, build_profile_id):
        self.app = app
        self.module = module
        self.detail = detail
        self.detail_type = detail_type
        self.cols_by_tile_field = {col.case_tile_field: col for col in self.detail.columns}
        self.build_profile_id = build_profile_id

    def build_case_tile_detail(self):
        """
        Return a Detail node from an apps.app_manager.models.Detail that is
        configured to use case tiles.

        This method does so by injecting the appropriate strings into a template
        string.
        """
        # Get template context
        context = self._get_base_context()
        for template_field in self.tile_fields:
            column = self._get_matched_detail_column(template_field)
            context[template_field] = self._get_column_context(column)

        # Populate the template
        detail_as_string = self._case_tile_template_string.format(**context)
        return load_xmlobject_from_string(detail_as_string, xmlclass=Detail)

    def _get_matched_detail_column(self, case_tile_field):
        """
        Get the detail column that should populate the given case tile field
        """
        column = self.cols_by_tile_field.get(case_tile_field, None)
        if column is None:
            raise SuiteError(
                'No column was mapped to the "{}" case tile field'.format(
                    case_tile_field
                )
            )
        return column

    def _get_base_context(self):
        """
        Get the basic context variables for interpolation into the
        case tile detail template string
        """
        return {
            "detail_id": id_strings.detail(self.module, self.detail_type),
            "title_text_id": id_strings.detail_title_locale(self.detail_type),
        }

    def _get_column_context(self, column):
        from corehq.apps.app_manager.detail_screen import get_column_generator
        default_lang = self.app.default_language if not self.build_profile_id \
            else self.app.build_profiles[self.build_profile_id].langs[0]
        if column.useXpathExpression:
            xpath_function = escape(column.field, {'"': '&quot;'})
        else:
            xpath_function = escape(get_column_generator(
                self.app, self.module, self.detail, column).xpath_function,
                {'"': '&quot;'})
        context = {
            "xpath_function": xpath_function,
            "locale_id": id_strings.detail_column_header_locale(
                self.module, self.detail_type, column,
            ),
            # Just using default language for now
            # The right thing to do would be to reference the app_strings.txt I think
            "prefix": escape(
                column.header.get(default_lang, "")
            )
        }
        if column.enum and column.format != "enum" and column.format != "conditional-enum":
            raise SuiteError(
                'Expected case tile field "{}" to be an id mapping with keys {}.'.format(
                    column.case_tile_field,
                    ", ".join(['"{}"'.format(i.key) for i in column.enum])
                )
            )

        context['variables'] = ''
        if column.format == "enum" or column.format == 'conditional-enum':
            context["variables"] = self._get_enum_variables(column)
        return context

    def _get_enum_variables(self, column):
        variables = []
        for i, mapping in enumerate(column.enum):
            variables.append(
                XpathVariable(
                    name=mapping.key_as_variable,
                    locale_id=id_strings.detail_column_enum_variable(
                        self.module, self.detail_type, column, mapping.key_as_variable
                    )
                ).serialize()
            )
        return ''.join([bytes(variable).decode('utf-8') for variable in variables])

    @property
    @memoized
    def _case_tile_template_string(self):
        """
        Return a string suitable for building a case tile detail node
        through `String.format`.
        """
        with open(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "case_tile_templates", "tdh.txt"),
            encoding='utf-8'
        ) as f:
            return f.read()
