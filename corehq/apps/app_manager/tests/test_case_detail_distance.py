from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.apps.app_manager.models import SortElement
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


class CaseDetailDistance(SimpleTestCase, TestXmlMixin):

    def setUp(self):
        self.factory = AppFactory(build_version='2.26')
        self.factory.new_basic_module('registration', 'patient registration')
        module = self.factory.app.get_module(0)
        self.case_details = module.case_details

    def test_short_detail_xml(self):
        short = self.case_details.short
        short.display = 'short'
        short_column = short.get_column(0)
        short_column.format = 'distance'

        suite = self.factory.app.create_suite()
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
                            <xpath function="if(here() = '' or case_name = '', '', concat(round(distance(case_name, here()) div 100) div 10, ' km'))"/>
                        </text>
                    </template>
                    <sort direction="ascending" order="1" type="double">
                        <text>
                                <xpath function="if(case_name = '', 2147483647, round(distance(case_name, here())))"/>
                        </text>
                    </sort>
                </field>
            </partial>
            """,
            suite,
            template_xpath
        )

    def test_short_detail_xml_with_sort(self):
        short = self.case_details.short
        short.display = 'short'
        short_column = short.get_column(0)
        short.sort_elements.append(
            SortElement(
                field=short_column.field,
                type='distance',
                direction='descending',
            )
        )

        suite = self.factory.app.create_suite()
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
                            <xpath function="case_name"/>
                        </text>
                    </template>
                    <sort direction="descending" order="1" type="double">
                        <text>
                            <xpath function="if(case_name = '', 2147483647, round(distance(case_name, here())))"/>
                        </text>
                    </sort>
                </field>
            </partial>
            """,
            suite,
            template_xpath
        )

    def test_short_detail_xml_sort_only(self):
        short = self.case_details.short
        short.display = 'short'
        short.sort_elements.append(
            SortElement(
                field='gps',
                type='distance',
                direction='descending',
            )
        )

        suite = self.factory.app.create_suite()
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
                            <xpath function="case_name"/>
                        </text>
                    </template>
                </field>
                <field>
                    <header width="0">
                        <text/>
                    </header>
                    <template width="0">
                        <text>
                            <xpath function="gps"/>
                        </text>
                    </template>
                    <sort direction="descending" order="1" type="double">
                        <text>
                            <xpath function="if(gps = '', 2147483647, round(distance(gps, here())))"/>
                        </text>
                    </sort>
                </field>
            </partial>
            """,
            suite,
            template_xpath
        )

    def test_long_detail_xml(self):
        long_ = self.case_details.long
        long_.display = 'long'
        long_column = long_.get_column(0)
        long_column.format = 'distance'

        suite = self.factory.app.create_suite()
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
                            <xpath function="if(here() = '' or case_name = '', '', concat(round(distance(case_name, here()) div 100) div 10, ' km'))"/>
                        </text>
                    </template>
                </field>
            </partial>
            """,
            suite,
            template_xpath
        )
