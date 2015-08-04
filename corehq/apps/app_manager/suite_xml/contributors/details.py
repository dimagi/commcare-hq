import os
from xml.sax.saxutils import escape
from eulxml.xmlmap.core import load_xmlobject_from_string
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import RETURN_TO, SCHEDULE_PHASE, SCHEDULE_LAST_VISIT
from corehq.apps.app_manager.exceptions import SuiteError, ScheduleError
from corehq.apps.app_manager.suite_xml.basic import SectionSuiteContributor
from corehq.apps.app_manager.suite_xml.contributors.entries import EntriesHelper
from corehq.apps.app_manager.suite_xml.utils import get_detail_column_infos, FIELD_TYPE_SCHEDULE
from corehq.apps.app_manager.suite_xml.xml import Detail, Text, StackDatum, PushFrame, Stack, Action, Display, Response, \
    Extra, Lookup, DetailVariable
from corehq.apps.app_manager.xpath import XPath, ScheduleFixtureInstance
from dimagi.utils.decorators.memoized import memoized


class DetailContributor(SectionSuiteContributor):
    section = 'details'
    
    def get_section_contributions(self):
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
                DetailContributor.detail_variables(module, detail, detail_column_infos[start:end])
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
            if module.case_list_form.form_id and detail_type.endswith('short') and \
                    not (hasattr(module, 'parent_select') and module.parent_select.active):
                # add form action to detail
                form = self.app.get_form(module.case_list_form.form_id)

                d.action = Action(
                    display=Display(
                        text=Text(locale_id=id_strings.case_list_form_locale(module)),
                        media_image=module.case_list_form.media_image,
                        media_audio=module.case_list_form.media_audio,
                    ),
                    stack=Stack()
                )
                frame = PushFrame()
                frame.add_command(XPath.string(id_strings.form_command(form)))

                if form.form_type == 'module_form':
                    datums_meta = self.get_case_datums_basic_module(form.get_module(), form)
                elif form.form_type == 'advanced_form':
                    datums_meta, _ = self.get_datum_meta_assertions_advanced(form.get_module(), form)
                    datums_meta.extend(EntriesHelper.get_new_case_id_datums_meta(form))

                for meta in datums_meta:
                    if meta['requires_selection']:
                        raise SuiteError("Form selected as case list form requires a case: {}".format(form.unique_id))
                    s_datum = meta['datum']
                    frame.add_datum(StackDatum(id=s_datum.id, value=s_datum.function))

                frame.add_datum(StackDatum(id=RETURN_TO, value=XPath.string(id_strings.menu_id(module))))
                d.action.stack.add_frame(frame)

            try:
                if not self.app.enable_multi_sort:
                    d.fields[0].sort = 'default'
            except IndexError:
                pass
            else:
                # only yield the Detail if it has Fields
                return d
    
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
                os.path.dirname(__file__), "case_tile_templates", "tdh.txt"
        )) as f:
            return f.read().decode('utf-8')

    @staticmethod
    def detail_variables(module, detail, detail_column_infos):
        has_schedule_columns = any(ci.column.field_type == FIELD_TYPE_SCHEDULE for ci in detail_column_infos)
        if hasattr(module, 'has_schedule') and \
                module.has_schedule and \
                module.all_forms_require_a_case and \
                has_schedule_columns:
            forms_due = []
            for form in module.get_forms():
                if not (form.schedule and form.schedule.anchor):
                    raise ScheduleError('Form in schedule module is missing schedule: %s' % form.default_name())

                fixture_id = id_strings.schedule_fixture(form)
                anchor = form.schedule.anchor

                # @late_window = '' or today() <= (date(edd) + int(@due) + int(@late_window))
                within_window = XPath.or_(
                    XPath('@late_window').eq(XPath.string('')),
                    XPath('today() <= ({} + {} + {})'.format(
                        XPath.date(anchor),
                        XPath.int('@due'),
                        XPath.int('@late_window'))
                    )
                )

                due_first = ScheduleFixtureInstance(fixture_id).visit().\
                    select_raw(within_window).\
                    select_raw("1").slash('@due')

                # current_schedule_phase = 1 and anchor != '' and (
                #   instance(...)/schedule/@expires = ''
                #   or
                #   today() < (date(anchor) + instance(...)/schedule/@expires)
                # )
                expires = ScheduleFixtureInstance(fixture_id).expires()
                valid_not_expired = XPath.and_(
                    XPath(SCHEDULE_PHASE).eq(form.id + 1),
                    XPath(anchor).neq(XPath.string('')),
                    XPath.or_(
                        XPath(expires).eq(XPath.string('')),
                        "today() < ({} + {})".format(XPath.date(anchor), expires)
                    ))

                visit_num_valid = XPath('@id > {}'.format(
                    SCHEDULE_LAST_VISIT.format(form.schedule_form_id)
                ))

                due_not_first = ScheduleFixtureInstance(fixture_id).visit().\
                    select_raw(visit_num_valid).\
                    select_raw(within_window).\
                    select_raw("1").slash('@due')

                name = 'next_{}'.format(form.schedule_form_id)
                forms_due.append(name)

                def due_date(due_days):
                    return '{} + {}'.format(XPath.date(anchor), XPath.int(due_days))

                xpath_phase_set = XPath.if_(valid_not_expired, due_date(due_not_first), 0)
                if form.id == 0:  # first form must cater for empty phase
                    yield DetailVariable(
                        name=name,
                        function=XPath.if_(
                            XPath(SCHEDULE_PHASE).eq(XPath.string('')),
                            due_date(due_first),
                            xpath_phase_set
                        )
                    )
                else:
                    yield DetailVariable(name=name, function=xpath_phase_set)

            yield DetailVariable(
                name='next_due',
                function='min({})'.format(','.join(forms_due))
            )

            yield DetailVariable(
                name='is_late',
                function='next_due < today()'
            )
