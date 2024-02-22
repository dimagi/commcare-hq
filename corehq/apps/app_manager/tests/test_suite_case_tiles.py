from django.test import SimpleTestCase

from corehq.apps.app_manager.exceptions import SuiteValidationError
from corehq.apps.app_manager.models import (
    Application,
    CaseSearch,
    CaseSearchProperty,
    DetailColumn,
    MappingItem,
    Module,
    SortElement,
)
from corehq.apps.app_manager.suite_xml.features.case_tiles import CaseTileTemplates, case_tile_template_config
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    SuiteMixin,
    patch_get_xform_resource_overrides,
)
from corehq.util.test_utils import flag_enabled


def add_columns_for_case_details(_module):
    _module.case_details.short.columns = [
        DetailColumn(
            header={'en': 'a'},
            model='case',
            field='a',
            format='plain',
            case_tile_field='header'
        ),
        DetailColumn(
            header={'en': 'b'},
            model='case',
            field='b',
            format='plain',
            case_tile_field='top_left'
        ),
        DetailColumn(
            header={'en': 'c'},
            model='case',
            field='c',
            format='enum',
            enum=[
                MappingItem(key='male', value={'en': 'Male'}),
                MappingItem(key='female', value={'en': 'Female'}),
            ],
            case_tile_field='sex'
        ),
        DetailColumn(
            header={'en': 'd'},
            model='case',
            field='d',
            format='address',
            case_tile_field='bottom_left'
        ),
        DetailColumn(
            header={'en': 'e'},
            model='case',
            field='e',
            format='date',
            case_tile_field='date'
        ),
    ]


def add_columns_for_one_one_two_case_details(_module):
    _module.case_details.short.columns = [
        DetailColumn(
            header={'en': 'a'},
            model='case',
            field='a',
            format='plain',
            case_tile_field='title'
        ),
        DetailColumn(
            header={'en': 'b'},
            model='case',
            field='b',
            format='plain',
            case_tile_field='top'
        ),
        DetailColumn(
            header={'en': 'c'},
            model='case',
            field='c',
            format='address',
            case_tile_field='bottom_left'
        ),
        DetailColumn(
            header={'en': 'd'},
            model='case',
            field='d',
            format='date',
            case_tile_field='bottom_right'
        ),
        DetailColumn(
            header={'en': 'e'},
            model='case',
            field='e',
            format='address',
            case_tile_field='map'
        ),
        DetailColumn(
            header={'en': 'e'},
            model='case',
            field='e',
            format='address-popup',
            case_tile_field='map_popup'
        ),
    ]


@patch_get_xform_resource_overrides()
class SuiteCaseTilesTest(SimpleTestCase, SuiteMixin):
    file_path = ('data', 'suite')

    # Keeps the number of columns in parity with what mobile allows
    def test_case_tile_column_count(self):
        for choice in CaseTileTemplates.choices:
            template_name = choice[0]
            template_grid = case_tile_template_config(template_name).grid

            for field in template_grid.values():
                absolute_width = field.get('x') + field.get('width')
                if absolute_width > 12:
                    message = "Number of columns in template '{}' " \
                        "exceeds the limit of 12".format(template_name)
                    raise AssertionError(message)

    def ensure_module_session_datum_xml(self, factory, detail_inline_attr, detail_persistent_attr):
        suite = factory.app.create_suite()
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    {detail_confirm_attr}
                    {detail_inline_attr}
                    {detail_persistent_attr}
                    detail-select="m1_case_short"
                    id="case_id_load_person_0"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """.format(detail_confirm_attr='detail-confirm="m1_case_long"' if not detail_inline_attr else '',
                       detail_inline_attr=detail_inline_attr,
                       detail_persistent_attr=detail_persistent_attr),
            suite,
            'entry/command[@id="m1-f0"]/../session/datum',
        )

    def test_case_tile_suite(self, *args):
        self._test_generic_suite("app_case_tiles", "suite-case-tiles")

    def test_case_tile_pull_down(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        module.case_details.short.persist_tile_on_forms = True
        module.case_details.short.pull_down_tile = True
        add_columns_for_case_details(module)

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        self.assertXmlPartialEqual(
            self.get_xml('case_tile_pulldown_session'),
            app.create_suite(),
            "./entry/session"
        )

    def test_case_tile_format_propagated(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        module.case_details.short.use_case_tiles = True
        add_columns_for_case_details(module)

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        self.assertXmlPartialEqual(
            self.get_xml('case_tile_template_format'),
            app.create_suite(),
            "./detail[@id='m0_case_short']/field[5]/template"
        )

    def test_inline_case_detail_from_another_module(self, *args):
        factory = AppFactory()
        module0, form0 = factory.new_advanced_module("m0", "person")
        factory.form_requires_case(form0, "person")
        module0.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module0)

        module1, form1 = factory.new_advanced_module("m1", "person")
        factory.form_requires_case(form1, "person")

        # not configured to use other module's persistent case tile so
        # has no detail-inline and detail-persistent attr
        self.ensure_module_session_datum_xml(factory, '', '')

        # configured to use other module's persistent case tile
        module1.case_details.short.persistent_case_tile_from_module = module0.unique_id
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')

        # configured to use other module's persistent case tile that has custom xml
        module0.case_details.short.case_tile_template = None
        module0.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')
        module0.case_details.short.custom_xml = ''
        module0.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value

        # configured to use pull down tile from the other module
        module1.case_details.short.pull_down_tile = True
        self.ensure_module_session_datum_xml(factory, 'detail-inline="m0_case_long"',
                                             'detail-persistent="m0_case_short"')

        # set to use persistent case tile of its own as well but it would still
        # persists case tiles and detail inline from another module
        module1.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        module1.case_details.short.persist_tile_on_forms = True
        add_columns_for_case_details(module1)
        self.ensure_module_session_datum_xml(factory, 'detail-inline="m0_case_long"',
                                             'detail-persistent="m0_case_short"')

        # set to use case tile from a module that does not support case tiles anymore
        # and has own persistent case tile as well
        # So now detail inline from its own details
        module0.case_details.short.case_tile_template = None
        self.ensure_module_session_datum_xml(factory, 'detail-inline="m1_case_long"',
                                             'detail-persistent="m1_case_short"')

        # set to use case tile from a module that does not support case tiles anymore
        # and does not have its own persistent case tile as well
        module1.case_details.short.case_tile_template = None
        self.ensure_module_session_datum_xml(factory, '', '')

    def test_persistent_case_tiles_from_another_module(self, *args):
        factory = AppFactory()
        module0, form0 = factory.new_advanced_module("m0", "person")
        factory.form_requires_case(form0, "person")
        module0.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module0)

        module1, form1 = factory.new_advanced_module("m1", "person")
        factory.form_requires_case(form1, "person")

        # not configured to use other module's persistent case tile so
        # has no detail-persistent attr
        self.ensure_module_session_datum_xml(factory, '', '')

        # configured to use other module's persistent case tile
        module1.case_details.short.persistent_case_tile_from_module = module0.unique_id
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')

        # configured to use other module's persistent case tile that has custom xml
        module0.case_details.short.case_tile_template = None
        module0.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')
        module0.case_details.short.custom_xml = ''
        module0.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value

        # set to use persistent case tile of its own as well but it would still
        # persists case tiles from another module
        module1.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        module1.case_details.short.persist_tile_on_forms = True
        add_columns_for_case_details(module1)
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m0_case_short"')

        # set to use case tile from a module that does not support case tiles anymore
        # and has own persistent case tile as well
        module0.case_details.short.case_tile_template = None
        self.ensure_module_session_datum_xml(factory, '', 'detail-persistent="m1_case_short"')

        # set to use case tile from a module that does not support case tiles anymore
        # and does not have its own persistent case tile as well
        module1.case_details.short.case_tile_template = None
        self.ensure_module_session_datum_xml(factory, '', '')

    def test_persistent_case_tiles_in_advanced_forms(self, *args):
        """
        Test that the detail-persistent attributes is set correctly when persistent
        case tiles are used on advanced forms.
        """
        factory = AppFactory()
        module, form = factory.new_advanced_module("my_module", "person")
        factory.form_requires_case(form, "person")
        module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        module.case_details.short.persist_tile_on_forms = True
        suite = factory.app.create_suite()

        # The relevant check is really that detail-persistent="m0_case_short"
        # but assertXmlPartialEqual xpath implementation doesn't currently
        # support selecting attributes
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    detail-confirm="m0_case_long"
                    detail-persistent="m0_case_short"
                    detail-select="m0_case_short"
                    id="case_id_load_person_0"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """,
            suite,
            "entry/session/datum"
        )

    def test_persistent_case_tiles_in_advanced_module_case_lists(self, *args):
        """
        Test that the detail-persistent attributes is set correctly when persistent
        case tiles are used on advanced module case lists
        """
        factory = AppFactory()
        module, form = factory.new_advanced_module("my_module", "person")
        factory.form_requires_case(form, "person")
        module.case_list.show = True
        module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        module.case_details.short.persist_tile_on_forms = True
        suite = factory.app.create_suite()

        # The relevant check is really that detail-persistent="m0_case_short"
        # but assertXmlPartialEqual xpath implementation doesn't currently
        # support selecting attributes
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    detail-confirm="m0_case_long"
                    detail-persistent="m0_case_short"
                    detail-select="m0_case_short"
                    id="case_id_case_person"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """,
            suite,
            'entry/command[@id="m0-case-list"]/../session/datum',
        )

    def test_persistent_case_name_in_forms(self, *args):
        """
        Test that the detail-persistent attributes are set correctly when the
        module is configured to persist the case name at the top of the form.
        Also confirm that the appropriate <detail> element is added to the suite.
        """
        factory = AppFactory()
        module, form = factory.new_basic_module("my_module", "person")
        factory.form_requires_case(form, "person")
        module.case_details.short.persist_case_context = True
        suite = factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <detail id="m0_persistent_case_context">
                    <title>
                        <text/>
                    </title>
                    <field>
                        <style font-size="large" horz-align="center" show-border="false" show-shading="false">
                            <grid grid-height="1" grid-width="12" grid-x="0" grid-y="0"/>
                        </style>
                        <header>
                            <text/>
                        </header>
                        <template>
                            <text>
                                <xpath function="case_name"/>
                            </text>
                        </template>
                    </field>
                </detail>
            </partial>
            """,
            suite,
            "detail[@id='m0_persistent_case_context']"
        )

        # The attribute we care about here is detail-persistent="m0_persistent_case_context"
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    detail-confirm="m0_case_long"
                    detail-persistent="m0_persistent_case_context"
                    detail-select="m0_case_short"
                    id="case_id"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """,
            suite,
            "entry/session/datum"
        )

    def test_persistent_case_name_when_tiles_enabled(self, *args):
        """
        Confirm that the persistent case name context is not added when case tiles
        are configured to persist in forms
        """
        factory = AppFactory()
        module, form = factory.new_advanced_module("my_module", "person")
        factory.form_requires_case(form, "person")
        module.case_details.short.custom_xml = '<detail id="m0_case_short"></detail>'
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        module.case_details.short.persist_tile_on_forms = True
        module.case_details.short.persist_case_context = True
        suite = factory.app.create_suite()

        self.assertXmlDoesNotHaveXpath(suite, "detail[@id='m0_persistent_case_context']")
        self.assertXmlPartialEqual(
            """
            <partial>
                <datum
                    detail-confirm="m0_case_long"
                    detail-persistent="m0_case_short"
                    detail-select="m0_case_short"
                    id="case_id_load_person_0"
                    nodeset="instance('casedb')/casedb/case[@case_type='person'][@status='open']"
                    value="./@case_id"
                />
            </partial>
            """,
            suite,
            "entry/session/datum"
        )

    def test_custom_xml_with_wrong_module_index(self, *args):
        factory = AppFactory()
        module, form = factory.new_advanced_module("my_module", "person")
        # This should be 'm0_case_short'
        module.case_details.short.custom_xml = '<detail id="m1_case_short"></detail>'
        with self.assertRaises(SuiteValidationError):
            factory.app.create_suite()

    @flag_enabled('CASE_LIST_TILE')
    @flag_enabled('USH_EMPTY_CASE_LIST_TEXT')
    def test_case_tile_no_items_text(self, *args):
        factory = AppFactory(build_version='2.54.0')
        factory.new_basic_module("my_module", "person")

        suite = factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <no_items_text>
                    <text>
                        <locale id="m0_no_items_text"/>
                    </text>
                </no_items_text>
            </partial>
            """,
            suite,
            "detail[@id='m0_case_short']/no_items_text[1]",
        )

    @flag_enabled("USH_CASE_CLAIM_UPDATES")
    def test_case_tile_with_case_search(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        add_columns_for_case_details(module)

        module.search_config = CaseSearch(
            properties=[
                CaseSearchProperty(name='name', label={'en': 'Name'}),
            ],
            auto_launch=True,
        )
        module.assign_references()

        form = app.new_form(0, "Untitled Form", None)
        form.xmlns = 'http://id_m0-f0'
        form.requires = 'case'

        # case list detail
        self.assertXmlPartialEqual(
            """
            <partial>
              <action redo_last="false"
                auto_launch="$next_input = '' or count(instance('casedb')/casedb/case[@case_id=$next_input]) = 0">
                <display>
                  <text>
                    <locale id="case_search.m0"/>
                  </text>
                </display>
                <stack>
                  <push>
                    <mark/>
                    <command value="'search_command.m0'"/>
                  </push>
                </stack>
              </action>
            </partial>
            """,
            app.create_suite(),
            # action[1] is the reg from case list action hard-coded into the default template
            "detail[@id='m0_case_short']/action[2]",
        )

        # case search detail
        self.assertXmlPartialEqual(
            """
            <partial>
              <action redo_last="true" auto_launch="false()">
                <display>
                  <text>
                    <locale id="case_search.m0.again"/>
                  </text>
                </display>
                <stack>
                  <push>
                    <mark/>
                    <command value="'search_command.m0'"/>
                  </push>
                </stack>
              </action>
            </partial>
            """,
            app.create_suite(),
            # action[1] is the reg from case list action hard-coded into the default template
            "detail[@id='m0_search_short']/action[2]",
        )

    def test_case_tile_with_sorting(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module("my_module", "person")
        module.case_details.short.case_tile_template = CaseTileTemplates.ONE_ONE_TWO.value
        module.case_details.short.display = 'short'
        add_columns_for_one_one_two_case_details(module)
        sort_elements = [
            SortElement(field='b', direction='ascending', type='plain'),
            SortElement(field='a', direction='ascending', type='plain')
        ]
        module.case_details.short.sort_elements.extend(sort_elements)
        suite = factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <sort direction="ascending" order="2" type="string">
                    <text>
                        <xpath function="a"/>
                    </text>
                </sort>
            </partial>
            """,
            suite,
            './detail[@id="m0_case_short"]/field[1]/sort',
        )

        self.assertXmlPartialEqual(
            """
            <partial>
                <sort direction="ascending" order="1" type="string">
                    <text>
                        <xpath function="b"/>
                    </text>
                </sort>
            </partial>
            """,
            suite,
            './detail[@id="m0_case_short"]/field[2]/sort',
        )

        self.assertXmlPartialEqual(
            """
            <partial>
                <sort type="string">
                    <text>
                        <xpath function="d"/>
                    </text>
                </sort>
            </partial>
            """,
            suite,
            './detail[@id="m0_case_short"]/field[4]/sort',
        )

    def test_case_tile_with_register_from_case_list(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module("my_module", "person")
        module.case_details.short.case_tile_template = CaseTileTemplates.ONE_ONE_TWO.value
        module.case_details.short.display = 'short'
        add_columns_for_one_one_two_case_details(module)

        reg_form = factory.new_form(module)
        reg_form.actions.open_case.condition.type = 'always'

        module.case_list_form.form_id = str(reg_form.get_unique_id())
        module.case_list_form.label = {"en": "Add new patient"}

        suite = factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <action>
                    <display>
                        <text>
                            <locale id="case_list_form.m0"/>
                        </text>
                    </display>
                    <stack>
                        <push>
                            <command value="'m0-f1'"/>
                            <datum id="case_id_new_person_0" value="uuid()"/>
                            <datum id="return_to" value="'m0'"/>
                        </push>
                    </stack>
                </action>
            </partial>
            """,
            suite,
            "detail[@id='m0_case_short']/action[1]",
        )
        self.assertXmlDoesNotHaveXpath(suite, "detail[@id='m0_case_short']/action[2]")

    def test_case_tile_without_register_from_case_list_because_of_person_simple(self, *args):
        factory = AppFactory()
        module, form = factory.new_basic_module("my_module", "person")
        module.case_details.short.case_tile_template = CaseTileTemplates.PERSON_SIMPLE.value
        module.case_details.short.display = 'short'
        add_columns_for_case_details(module)

        reg_form = factory.new_form(module)
        reg_form.actions.open_case.condition.type = 'always'

        module.case_list_form.form_id = str(reg_form.get_unique_id())
        module.case_list_form.label = {"en": "Add new patient"}

        suite = factory.app.create_suite()

        self.assertXmlPartialEqual(
            """
            <partial>
                <action>
                    <display>
                        <text>
                            <locale id="forms.m0f0"/>
                        </text>
                        <media image="jr://media/plus.png"/>
                    </display>
                    <stack>
                        <push>
                            <command value="'m0-f0'"/>
                            <datum id="case_id_new_rec_child_0" value="uuid()"/>
                        </push>
                    </stack>
                </action>
            </partial>
            """,
            suite,
            "detail[@id='m0_case_short']/action[1]",
        )
