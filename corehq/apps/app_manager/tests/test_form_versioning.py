from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.testcases import TestCase, SimpleTestCase
from mock import patch

from corehq.apps.app_manager.suite_xml import xml_models as suite_models
from corehq.apps.app_manager.models import Application, Module, Form, import_app, FormLink
from corehq.apps.app_manager.tests.util import add_build, patch_default_builds
from corehq.apps.builds.models import BuildSpec


BLANK_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" ?>
<h:html xmlns:h="http://www.w3.org/1999/xhtml" xmlns:orx="http://openrosa.org/jr/xforms" xmlns="http://www.w3.org/2002/xforms" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:jr="http://openrosa.org/javarosa">
    <h:head>
        <h:title>New Form</h:title>
        <model>
            <instance>
                <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="{xmlns}" uiVersion="1" version="1" name="New Form">
                    <question1 />
                </data>
            </instance>
            <bind nodeset="/data/question1" type="xsd:string" />
            <itext>
                <translation lang="en" default="">
                    <text id="question1-label">
                        <value>question1</value>
                    </text>
                </translation>
            </itext>
        </model>
    </h:head>
    <h:body>
        <input ref="/data/question1">
            <label ref="jr:itext('question1-label')" />
        </input>
    </h:body>
</h:html>
"""


class FormVersioningTest(TestCase):

    @patch_default_builds
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test(self, mock):
        add_build(version='2.7.0', build_number=20655)
        domain = 'form-versioning-test'

        # set up inital app
        app = Application.new_app(domain, 'Foo')
        app.modules.append(Module(forms=[Form(), Form()]))
        app.build_spec = BuildSpec.from_string('2.7.0/latest')
        app.get_module(0).get_form(0).source = BLANK_TEMPLATE.format(xmlns='xmlns-0.0')
        app.get_module(0).get_form(1).source = BLANK_TEMPLATE.format(xmlns='xmlns-1')
        app.save()

        # make a build
        build1 = app.make_build()
        build1.save()

        # modify first form
        app.get_module(0).get_form(0).source = BLANK_TEMPLATE.format(xmlns='xmlns-0.1')
        app.save()

        # make second build
        build2 = app.make_build()
        build2.save()

        # modify first form
        app.get_module(0).get_form(0).source = BLANK_TEMPLATE.format(xmlns='xmlns-0.2')
        app.save()
        app.save()
        app.save()

        # make third build
        build3 = app.make_build()
        build3.save()

        self.assertEqual(self.get_form_versions(build1), [1, 1])
        self.assertEqual(self.get_form_versions(build2), [2, 1])
        self.assertEqual(self.get_form_versions(build3), [5, 1])

        # revert to build2
        app = app.make_reversion_to_copy(build2)
        app.save()

        # make reverted build
        build4 = app.make_build()
        build4.save()

        self.assertEqual(self.get_form_versions(build4), [6, 1])

        # copy app
        xxx_app = import_app(app.export_json(dump_json=False), domain)

        # make build of copy
        xxx_build1 = xxx_app.make_build()
        xxx_build1.save()

        # modify first form of copy app
        xxx_app.get_module(0).get_form(0).source = BLANK_TEMPLATE.format(xmlns='xmlns-0.xxx.0')
        xxx_app.save()

        # make second build of copy
        xxx_build2 = xxx_app.make_build()
        xxx_build2.save()

        self.assertEqual(self.get_form_versions(xxx_build1), [1, 1])
        self.assertEqual(self.get_form_versions(xxx_build2), [2, 1])

    @staticmethod
    def get_form_versions(build):
        from lxml import etree

        suite = suite_models.Suite(
            etree.fromstring(build.fetch_attachment('files/suite.xml'))
        )
        return [r.version for r in suite.xform_resources]


class FormIdTest(SimpleTestCase):

    def test_update_form_references_case_list_form(self):
        app = Application.new_app('domain', 'Foo')
        app.modules.append(Module(forms=[Form()]))
        app.modules.append(Module(forms=[Form()]))
        app.build_spec = BuildSpec.from_string('2.7.0/latest')
        app.get_module(0).get_form(0).source = BLANK_TEMPLATE.format(xmlns='xmlns-0.0')
        app.get_module(1).get_form(0).source = BLANK_TEMPLATE.format(xmlns='xmlns-1')

        original_form_id = app.get_module(1).get_form(0).unique_id
        app.get_module(0).case_list_form.form_id = original_form_id

        copy = Application.from_source(app.export_json(dump_json=False), 'domain')
        new_form_id = copy.get_module(1).get_form(0).unique_id
        self.assertNotEqual(original_form_id, new_form_id)
        self.assertEqual(new_form_id, copy.get_module(0).case_list_form.form_id)

    def test_update_form_references_form_link(self):
        app = Application.new_app('domain', 'Foo')
        app.modules.append(Module(forms=[Form()]))
        app.modules.append(Module(forms=[Form(), Form()]))
        app.build_spec = BuildSpec.from_string('2.7.0/latest')
        app.get_module(0).get_form(0).source = BLANK_TEMPLATE.format(xmlns='xmlns-0.0')
        app.get_module(1).get_form(0).source = BLANK_TEMPLATE.format(xmlns='xmlns-1')

        original_form_id1 = app.get_module(1).get_form(0).unique_id
        original_form_id2 = app.get_module(1).get_form(1).unique_id
        app.get_module(0).get_form(0).form_links = [
            FormLink(xpath="", form_id=original_form_id1),
            FormLink(xpath="", form_id=original_form_id2),
        ]

        copy = Application.from_source(app.export_json(dump_json=False), 'domain')
        new_form_id1 = copy.get_module(1).get_form(0).unique_id
        new_form_id2 = copy.get_module(1).get_form(1).unique_id
        self.assertNotEqual(original_form_id1, new_form_id1)
        self.assertNotEqual(original_form_id2, new_form_id2)
        self.assertEqual(new_form_id1, copy.get_module(0).get_form(0).form_links[0].form_id)
        self.assertEqual(new_form_id2, copy.get_module(0).get_form(0).form_links[1].form_id)
