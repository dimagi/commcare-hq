from __future__ import absolute_import
from collections import namedtuple
import os
from xml.sax.saxutils import escape

from eulxml.xmlmap.core import load_xmlobject_from_string

from corehq.apps.app_manager.const import RETURN_TO
from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_LEDGER
from corehq.apps.app_manager.suite_xml.contributors import SectionContributor
from corehq.apps.app_manager.suite_xml.post_process.instances import EntryInstances
from corehq.apps.app_manager.suite_xml.xml_models import Text, Xpath, Locale, Id, Header, Template, Field, Lookup, Extra, \
    Response, Detail, LocalizedAction, Stack, Action, Display, PushFrame, StackDatum
from corehq.apps.app_manager.suite_xml.features.scheduler import schedule_detail_variables
from corehq.apps.app_manager.util import create_temp_sort_column
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import SuiteError
from corehq.apps.app_manager.xpath import session_var, XPath
from dimagi.utils.decorators.memoized import memoized


class DetailContributor(SectionContributor):
    section_name = 'details'
    
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
                                    r.append(self.build_case_tile_detail(
                                        module, detail, detail_type
                                    ))
                                else:
                                    d = self.build_detail(
                                        module,
                                        detail_type,
                                        detail,
                                        detail_column_infos,
                                        list(detail.get_tabs()),
                                        id_strings.detail(module, detail_type),
                                        Text(locale_id=id_strings.detail_title_locale(
                                            module, detail_type
                                        )),
                                        0,
                                        len(detail_column_infos)
                                    )
                                    if d:
                                        r.append(d)
                if module.fixture_select.active:
                    d = Detail(
                        id=id_strings.fixture_detail(module),
                        title=Text(),
                    )
                    xpath = Xpath(function=module.fixture_select.display_column)
                    if module.fixture_select.localize:
                        template_text = Text(locale=Locale(child_id=Id(xpath=xpath)))
                    else:
                        template_text = Text(xpath_function=module.fixture_select.display_column)
                    fields = [Field(header=Header(text=Text()),
                                    template=Template(text=template_text),
                                    sort_node='')]

                    d.fields = fields
                    r.append(d)
        return r
    
    def build_detail(self, module, detail_type, detail, detail_column_infos,
                     tabs, id, title, start, end):
        """
        Recursively builds the Detail object.
        (Details can contain other details for each of their tabs)
        """
        from corehq.apps.app_manager.detail_screen import get_column_generator
        d = Detail(id=id, title=title)
        if tabs:
            tab_spans = detail.get_tab_spans()
            for tab in tabs:
                sub_detail = self.build_detail(
                    module,
                    detail_type,
                    detail,
                    detail_column_infos,
                    [],
                    None,
                    Text(locale_id=id_strings.detail_tab_title_locale(
                        module, detail_type, tab
                    )),
                    tab_spans[tab.id][0],
                    tab_spans[tab.id][1]
                )
                if sub_detail:
                    d.details.append(sub_detail)
            if len(d.details):
                return d
            else:
                return None

        # Base case (has no tabs)
        else:
            # Add lookup
            if detail.lookup_enabled and detail.lookup_action:
                d.lookup = Lookup(
                    name=detail.lookup_name or None,
                    action=detail.lookup_action,
                    image=detail.lookup_image or None,
                )
                d.lookup.extras = [Extra(**e) for e in detail.lookup_extras]
                d.lookup.responses = [Response(**r) for r in detail.lookup_responses]

            # Add variables
            variables = list(
                schedule_detail_variables(module, detail, detail_column_infos)
            )
            if variables:
                d.variables.extend(variables)

            # Add fields
            for column_info in detail_column_infos[start:end]:
                fields = get_column_generator(
                    self.app, module, detail,
                    detail_type=detail_type, *column_info
                ).fields
                d.fields.extend(fields)

            # Add actions
            if module.case_list_form.form_id and detail_type.endswith('short')\
                    and not module.put_in_root:
                self._add_action_to_detail(d, module)

            try:
                if not self.app.enable_multi_sort:
                    d.fields[0].sort = 'default'
            except IndexError:
                pass
            else:
                # only yield the Detail if it has Fields
                return d

    def _add_action_to_detail(self, detail, module):
        # add form action to detail
        form = self.app.get_form(module.case_list_form.form_id)

        if self.app.enable_localized_menu_media:
            case_list_form = module.case_list_form
            detail.action = LocalizedAction(
                menu_locale_id=id_strings.case_list_form_locale(module),
                media_image=bool(len(case_list_form.all_image_paths())),
                media_audio=bool(len(case_list_form.all_audio_paths())),
                image_locale_id=id_strings.case_list_form_icon_locale(module),
                audio_locale_id=id_strings.case_list_form_audio_locale(module),
                stack=Stack(),
                for_action_menu=True,
            )
        else:
            detail.action = Action(
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
                    raise SuiteError("Form selected as case list form requires a case "
                                     "but no matching case could be found: {}".format(form.unique_id))
                else:
                    frame.add_datum(StackDatum(
                        id=target_meta.datum.id,
                        value=session_var(source_dm.datum.id))
                    )
            else:
                s_datum = target_meta.datum
                frame.add_datum(StackDatum(id=s_datum.id, value=s_datum.function))

        frame.add_datum(StackDatum(id=RETURN_TO, value=XPath.string(id_strings.menu_id(module))))
        detail.action.stack.add_frame(frame)
    
    def build_case_tile_detail(self, module, detail, detail_type):
        """
        Return a Detail node from an apps.app_manager.models.Detail that is
        configured to use case tiles.

        This method does so by injecting the appropriate strings into a template
        string.
        """
        from corehq.apps.app_manager.detail_screen import get_column_xpath_generator

        template_args = {
            "detail_id": id_strings.detail(module, detail_type),
            "title_text_id": id_strings.detail_title_locale(
                module, detail_type
            )
        }
        # Get field/case property mappings

        cols_by_tile = {col.case_tile_field: col for col in detail.columns}
        for template_field in ["header", "top_left", "sex", "bottom_left", "date"]:
            column = cols_by_tile.get(template_field, None)
            if column is None:
                raise SuiteError(
                    'No column was mapped to the "{}" case tile field'.format(
                        template_field
                    )
                )
            template_args[template_field] = {
                "prop_name": get_column_xpath_generator(
                    self.app, module, detail, column
                ).xpath,
                "locale_id": id_strings.detail_column_header_locale(
                    module, detail_type, column,
                ),
                # Just using default language for now
                # The right thing to do would be to reference the app_strings.txt I think
                "prefix": escape(
                    column.header.get(self.app.default_language, "")
                )
            }
            if column.format == "enum":
                template_args[template_field]["enum_keys"] = {}
                for mapping in column.enum:
                    template_args[template_field]["enum_keys"][mapping.key] = \
                        id_strings.detail_column_enum_variable(
                            module, detail_type, column, mapping.key_as_variable
                        )
        # Populate the template
        detail_as_string = self._case_tile_template_string.format(**template_args)
        return load_xmlobject_from_string(detail_as_string, xmlclass=Detail)

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


class DetailsHelper(object):
    def __init__(self, app, modules=None):
        self.app = app
        self._modules = modules
        self.active_details = self._active_details()

    @property
    @memoized
    def modules(self):
        return self._modules or self.app.get_modules()

    def _active_details(self):
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

    # order is 1-indexed
    sort_elements = {s.field: (s, i + 1)
                     for i, s in enumerate(sort_elements)}
    columns = []
    for column in detail.get_columns():
        sort_element, order = sort_elements.pop(column.field, (None, None))
        columns.append(DetailColumnInfo(column, sort_element, order))

    # sort elements is now populated with only what's not in any column
    # add invisible columns for these
    sort_only = sorted(sort_elements.items(),
                       key=lambda (field, (sort_element, order)): order)

    for field, (sort_element, order) in sort_only:
        column = create_temp_sort_column(field, len(columns))
        columns.append(DetailColumnInfo(column, sort_element, order))
    return columns


def get_instances_for_module(app, module, additional_xpaths=None):
        """
        This method is used by CloudCare when filtering cases.
        """
        modules = app.get_modules()
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

        return EntryInstances.get_required_instances(xpaths)
