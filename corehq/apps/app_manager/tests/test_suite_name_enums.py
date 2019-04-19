# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import MappingItem
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import SuiteMixin, TestXmlMixin
from corehq.util.test_utils import flag_enabled


@flag_enabled('APP_BUILDER_CONDITIONAL_NAMES')
class SuiteNameEnumsTest(SimpleTestCase, TestXmlMixin, SuiteMixin):
    file_path = ('data', 'suite')
    case_type = 'patient'
    enum = [
        MappingItem(key='int(double(now())) mod 1 = 0', value={'en': 'evens'}),
        MappingItem(key='int(double(now())) mod 1 = 1', value={'en': 'odds'}),
    ]

    def setUp(self):
        self.factory = AppFactory(build_version='2.40.0', domain='domain')
        self.basic_module, self.basic_form = self.factory.new_basic_module('basic', self.case_type)
        self.basic_module.name_enum = self.enum
        self.basic_form.name_enum = self.enum

    def test_module(self):
        self.assertXmlPartialEqual(
            """
            <partial>
                <menu id="m0">
                    <text>
                        <xpath function="if(int(double(now())) mod 1 = 0, $h2cb17fc7, if(int(double(now())) mod 1 = 1, $h137bc41f, ''))">
                            <variable name="h2cb17fc7">
                                <locale id="m0.enum.h2cb17fc7"/>
                            </variable>
                            <variable name="h137bc41f">
                                <locale id="m0.enum.h137bc41f"/>
                            </variable>
                        </xpath>
                    </text>
                    <command id="m0-f0"/>
                </menu>
            </partial>
            """,
            self.factory.app.create_suite(),
            'menu[@id="m0"]',
        )

    def test_module_with_media(self):
        self.basic_module.media_audio = {'en': 'jr://file/commcare/audio/en/module0.mp3'}
        self.basic_module.media_image = {'en': 'jr://file/commcare/image/module0_en.png'}
        self.assertXmlPartialEqual(
            """
            <partial>
                <menu id="m0">
                    <display>
                        <text>
                            <xpath function="if(int(double(now())) mod 1 = 0, $h2cb17fc7, if(int(double(now())) mod 1 = 1, $h137bc41f, ''))">
                                <variable name="h2cb17fc7">
                                    <locale id="m0.enum.h2cb17fc7"/>
                                </variable>
                                <variable name="h137bc41f">
                                    <locale id="m0.enum.h137bc41f"/>
                                </variable>
                            </xpath>
                        </text>
                        <text form="image">
                            <locale id="modules.m0.icon"/>
                        </text>
                        <text form="audio">
                            <locale id="modules.m0.audio"/>
                        </text>
                    </display>
                    <command id="m0-f0"/>
                </menu>
            </partial>
            """,
            self.factory.app.create_suite(),
            'menu[@id="m0"]',
        )

    def test_report_module(self):
        self.report_module = self.factory.new_report_module('basic')
        self.report_module.name_enum = self.enum
        self.assertXmlPartialEqual(
            """
            <partial>
                <menu id="m1">
                    <text>
                        <xpath function="if(int(double(now())) mod 1 = 0, $h2cb17fc7, if(int(double(now())) mod 1 = 1, $h137bc41f, ''))">
                            <variable name="h2cb17fc7">
                                <locale id="m1.enum.h2cb17fc7"/>
                            </variable>
                            <variable name="h137bc41f">
                                <locale id="m1.enum.h137bc41f"/>
                            </variable>
                        </xpath>
                    </text>
                </menu>
            </partial>
            """,
            self.factory.app.create_suite(),
            'menu[@id="m1"]',
        )

    def test_form(self):
        self.assertXmlPartialEqual(
            """
            <partial>
                <entry>
                    <command id="m0-f0">
                        <text>
                            <xpath function="if(int(double(now())) mod 1 = 0, $h2cb17fc7, if(int(double(now())) mod 1 = 1, $h137bc41f, ''))">
                                <variable name="h2cb17fc7">
                                    <locale id="m0f0.enum.h2cb17fc7"/>
                                </variable>
                                <variable name="h137bc41f">
                                    <locale id="m0f0.enum.h137bc41f"/>
                                </variable>
                            </xpath>
                        </text>
                    </command>
                </entry>
            </partial>
            """,
            self.factory.app.create_suite(),
            'entry[1]',
        )

    def test_form_with_media(self):
        self.basic_form.media_audio = {'en': 'jr://file/commcare/audio/en/module0.mp3'}
        self.basic_form.media_image = {'en': 'jr://file/commcare/image/module0_en.png'}
        self.assertXmlPartialEqual(
            """
            <partial>
                <entry>
                    <command id="m0-f0">
                        <display>
                            <text>
                                <xpath function="if(int(double(now())) mod 1 = 0, $h2cb17fc7, if(int(double(now())) mod 1 = 1, $h137bc41f, ''))">
                                    <variable name="h2cb17fc7">
                                        <locale id="m0f0.enum.h2cb17fc7"/>
                                    </variable>
                                    <variable name="h137bc41f">
                                        <locale id="m0f0.enum.h137bc41f"/>
                                    </variable>
                                </xpath>
                            </text>
                            <text form="image">
                                <locale id="forms.m0f0.icon"/>
                            </text>
                            <text form="audio">
                                <locale id="forms.m0f0.audio"/>
                            </text>
                        </display>
                    </command>
                </entry>
            </partial>
            """,
            self.factory.app.create_suite(),
            'entry[1]',
        )
