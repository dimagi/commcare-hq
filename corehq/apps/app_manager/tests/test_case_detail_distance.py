from django.test import SimpleTestCase
from corehq.apps.app_manager.tests import AppFactory, TestXmlMixin


class CaseDetailDistance(SimpleTestCase, TestXmlMixin):

    def test_short_detail_xml(self):
        factory = AppFactory(build_version='2.26')
        factory.new_basic_module('registration', 'patient registration')
        module = factory.app.get_module(0)
        case_details = module.case_details
        short = case_details.short
        short.display = 'short'
        short_column = short.get_column(0)
        short_column.format = 'distance'

        suite = factory.app.create_suite()
        template_xpath = './detail[@id="m0_case_short"]/field'
        self.assertXmlHasXpath(suite, template_xpath)
        self.assertXmlPartialEqual(
            """
            <partial>
                <field>
                    <header>
                        <text>
                            <locale id="m0.case_short.case_name_1.header"/>
                        </text>
                    </header>
                    <template>
                        <text>
                            <xpath function="if(here() = '', '', if(case_name = '', '', concat(round(distance(case_name, here()) div 1000), ' km')))"/>
                        </text>
                    </template>
                    <sort direction="ascending" order="1" type="double">
                        <text>
                                <xpath function="round(distance(case_name, here()))"/>
                        </text>
                    </sort>
                </field>
            </partial>
            """,
            suite,
            template_xpath
        )

    def test_long_detail_xml(self):
        factory = AppFactory(build_version='2.26')
        factory.new_basic_module('registration', 'patient registration')
        module = factory.app.get_module(0)
        case_details = module.case_details
        long = case_details.long
        long.display = 'long'
        long_column = long.get_column(0)
        long_column.format = 'distance'

        suite = factory.app.create_suite()
        template_xpath = './detail[@id="m0_case_long"]/field'
        self.assertXmlHasXpath(suite, template_xpath)
        self.assertXmlPartialEqual(
            """
            <partial>
                <field>
                    <header>
                        <text>
                            <locale id="m0.case_long.case_name_1.header"/>
                        </text>
                    </header>
                    <template>
                        <text>
                            <xpath function="if(here() = '', '', if(case_name = '', '', concat(round(distance(case_name, here()) div 1000), ' km')))"/>
                        </text>
                    </template>
                </field>
            </partial>
            """,
            suite,
            template_xpath
        )
