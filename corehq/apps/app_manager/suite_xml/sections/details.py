from __future__ import absolute_import
from collections import namedtuple
import os
from xml.sax.saxutils import escape

from eulxml.xmlmap.core import load_xmlobject_from_string

from corehq.apps.app_manager.const import RETURN_TO
from corehq.apps.app_manager.id_strings import callout_header_locale
from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_LEDGER
from corehq.apps.app_manager.suite_xml.contributors import SectionContributor
from corehq.apps.app_manager.suite_xml.post_process.instances import EntryInstances
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
)
from corehq.apps.app_manager.suite_xml.features.scheduler import schedule_detail_variables
from corehq.apps.app_manager.util import create_temp_sort_column, module_offers_search,\
    get_sort_and_sort_only_columns
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import SuiteError
from corehq.apps.app_manager.xpath import session_var, XPath
from dimagi.utils.decorators.memoized import memoized


class DetailContributor(SectionContributor):
    section_name = 'details'

    def __init__(self, suite, app, modules, build_profile_id=None):
        super(DetailContributor, self).__init__(suite, app, modules)
        self.build_profile_id = build_profile_id

    def get_section_elements(self):
        r = []
        if not self.app.use_custom_suite:
            for module in self.modules:
                for detail_type, detail, enabled in module.get_details():
                    if enabled:
                        if detail.custom_xml:
                            d = load_xmlobject_from_string(
                                detail.custom_xml,
                                xmlclass=Detail
                            )
                            r.append(d)
                        else:
                            detail_column_infos = get_detail_column_infos(
                                detail,
                                include_sort=detail_type.endswith('short'),
                            )
                            if detail_column_infos:
                                if detail.use_case_tiles:
                                    helper = CaseTileHelper(self.app, module, detail,
                                                            detail_type, self.build_profile_id)
                                    r.append(helper.build_case_tile_detail())
                                else:
                                    d = self.build_detail(
                                        module,
                                        detail_type,
                                        detail,
                                        detail_column_infos,
                                        tabs=list(detail.get_tabs()),
                                        id=id_strings.detail(module, detail_type),
                                        title=Text(locale_id=id_strings.detail_title_locale(
                                            module, detail_type
                                        )),
                                    )
                                    if d:
                                        r.append(d)
                        if detail.persist_case_context and not detail.persist_tile_on_forms:
                            d = self._get_persistent_case_context_detail(module, detail.persistent_case_context_xml)
                            r.append(d)
                if module.fixture_select.active:
                    d = self._get_fixture_detail(module)
                    r.append(d)
        return r

    def build_detail(self, module, detail_type, detail, detail_column_infos,
                     tabs=None, id=None, title=None, nodeset=None, start=0, end=None):
        """
        Recursively builds the Detail object.
        (Details can contain other details for each of their tabs)
        """
        from corehq.apps.app_manager.detail_screen import get_column_generator
        d = Detail(id=id, title=title, nodeset=nodeset)
        if tabs:
            tab_spans = detail.get_tab_spans()
            for tab in tabs:
                sub_detail = self.build_detail(
                    module,
                    detail_type,
                    detail,
                    detail_column_infos,
                    title=Text(locale_id=id_strings.detail_tab_title_locale(
                        module, detail_type, tab
                    )),
                    nodeset=tab.nodeset if tab.has_nodeset else None,
                    start=tab_spans[tab.id][0],
                    end=tab_spans[tab.id][1]
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
                fields = get_column_generator(
                    self.app, module, detail,
                    detail_type=detail_type, *column_info
                ).fields
                d.fields.extend(fields)

            # Add actions
            if module.case_list_form.form_id and detail_type.endswith('short')\
                    and not module.put_in_root:
                target_form = self.app.get_form(module.case_list_form.form_id)
                if target_form.is_registration_form(module.case_type):
                    d.actions.append(self._get_reg_form_action(module))
            if module_offers_search(module) and detail_type.endswith('short') and not module.put_in_root:
                d.actions.append(self._get_case_search_action(module))

            try:
                if not self.app.enable_multi_sort:
                    d.fields[0].sort = 'default'
            except IndexError:
                pass
            else:
                # only yield the Detail if it has Fields
                return d

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

    def _get_reg_form_action(self, module):
        """
        Returns registration form action
        """
        form = self.app.get_form(module.case_list_form.form_id)

        if self.app.enable_localized_menu_media:
            case_list_form = module.case_list_form
            action = LocalizedAction(
                menu_locale_id=id_strings.case_list_form_locale(module),
                media_image=bool(len(case_list_form.all_image_paths())),
                media_audio=bool(len(case_list_form.all_audio_paths())),
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
                stack=Stack()
            )

        frame = PushFrame()
        frame.add_command(XPath.string(id_strings.form_command(form)))

        target_form_dm = self.entries_helper.get_datums_meta_for_form_generic(form)
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

    @staticmethod
    def _get_case_search_action(module):
        action = Action(
            display=Display(
                text=Text(locale_id=id_strings.case_search_locale(module))
            ),
            stack=Stack()
        )
        frame = PushFrame()
        frame.add_mark()
        frame.add_command(XPath.string(id_strings.search_command(module)))
        action.stack.add_frame(frame)
        return action

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


def get_detail_column_infos(detail, include_sort):
    """
    This is not intented to be a widely used format
    just a packaging of column info into a form most convenient for rendering
    """
    DetailColumnInfo = namedtuple('DetailColumnInfo',
                                  'column sort_element order')
    if not include_sort:
        return [DetailColumnInfo(column, None, None) for column in detail.get_columns()]

    if detail.sort_elements:
        sort_elements = detail.sort_elements
    else:
        sort_elements = get_default_sort_elements(detail)

    sort_only, sort_columns = get_sort_and_sort_only_columns(detail, sort_elements)

    columns = []
    for column in detail.get_columns():
        sort_element, order = sort_columns.pop(column.field, (None, None))
        columns.append(DetailColumnInfo(column, sort_element, order))

    for field, sort_element, order in sort_only:
        column = create_temp_sort_column(sort_element, order)
        columns.append(DetailColumnInfo(column, sort_element, order))
    return columns


def get_instances_for_module(app, module, additional_xpaths=None):
    """
    This method is used by CloudCare when filtering cases.
    """
    modules = list(app.get_modules())
    helper = DetailsHelper(app, modules)
    details = DetailContributor(None, app, modules).get_section_elements()
    detail_mapping = {detail.id: detail for detail in details}
    details_by_id = detail_mapping
    detail_ids = [helper.get_detail_id_safe(module, detail_type)
                  for detail_type, detail, enabled in module.get_details()
                  if enabled]
    detail_ids = filter(None, detail_ids)
    xpaths = set()

    if additional_xpaths:
        xpaths.update(additional_xpaths)

    for detail_id in detail_ids:
        xpaths.update(details_by_id[detail_id].get_all_xpaths())

    instances, _ = EntryInstances.get_required_instances(xpaths)
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
            "title_text_id": id_strings.detail_title_locale(
                self.module, self.detail_type
            )
        }

    def _get_column_context(self, column):
        from corehq.apps.app_manager.detail_screen import get_column_generator
        default_lang = self.app.default_language if not self.build_profile_id \
            else self.app.build_profiles[self.build_profile_id].langs[0]
        context = {
            "xpath_function": escape(get_column_generator(
                self.app, self.module, self.detail, column).xpath_function,
                {'"': '&quot;'}),
            "locale_id": id_strings.detail_column_header_locale(
                self.module, self.detail_type, column,
            ),
            # Just using default language for now
            # The right thing to do would be to reference the app_strings.txt I think
            "prefix": escape(
                column.header.get(default_lang, "")
            )
        }
        if column.format == "enum":
            context["enum_keys"] = self._get_enum_keys(column)
        return context

    def _get_enum_keys(self, column):
        keys = {}
        for mapping in column.enum:
            keys[mapping.key] = id_strings.detail_column_enum_variable(
                self.module, self.detail_type, column, mapping.key_as_variable
            )
        return keys

    @property
    @memoized
    def _case_tile_template_string(self):
        """
        Return a string suitable for building a case tile detail node
        through `String.format`.
        """
        with open(os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "case_tile_templates", "tdh.txt"
        )) as f:
            return f.read().decode('utf-8')
