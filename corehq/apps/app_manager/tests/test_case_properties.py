import os

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.app_manager.models import (Application, Module, APP_V2,
        OpenCaseAction, UpdateCaseAction, OpenSubCaseAction)
from corehq.apps.app_manager.util import get_all_case_properties
from corehq.apps.app_manager.case_references import (get_validated_references,
    RefType)


class CasePropertiesTest(TestCase):
    domain = 'test-domain'

    parent_type = 'foo'
    child_type = 'bar'

    # to ensure we're not getting incorrect results due to local state
    @property
    def this_app(self):
        return Application.get(self.this_app_id)

    @property
    def other_app1(self):
        return Application.get(self.other_app1_id)

    @property
    def other_app2(self):
        return Application.get(self.other_app2_id)

    def setUp(self):
        def read(filename):
            path = os.path.join(os.path.dirname(__file__), "data", filename)
            with open(path) as f:
                return f.read()

        create_domain(self.domain)

        this_app = Application.new_app(
                self.domain, "This App", application_version=APP_V2)

        this_app.add_module(Module.new_module("Parent Module", 'en'))
        parent_module = this_app.get_module(0)
        parent_module.case_type = self.parent_type
        
        parent_form = this_app.new_form(
                parent_module.id, name="Create Parent", lang='en')
        parent_form.actions.open_case = OpenCaseAction({
            "condition": {
                "answer": None,
                "doc_type": "FormActionCondition",
                "question": None,
                "type": "always"
            },
            "doc_type": "OpenCaseAction",
            "external_id": None,
            "name_path": "/data/name"
        })
        parent_form.actions.update_case = UpdateCaseAction({
            "condition": {
                "answer": None,
                "doc_type": "FormActionCondition",
                "question": None,
                "type": "always"
            },
            "doc_type": "UpdateCaseAction",
            "update": {
                "parent_property_1": "/data/parent_property_1"
            }
        })

        child_form = this_app.new_form(
                parent_module.id, name="Create Child", lang='en')
        # trigger subcase update detection
        child_form.actions.update_case = UpdateCaseAction({
            "condition": {
                "answer": None,
                "doc_type": "FormActionCondition",
                "question": None,
                "type": "always"
            },
            "doc_type": "UpdateCaseAction",
            "update": {}
        })
        child_form.actions.subcases.append(
            OpenSubCaseAction({
                "case_name": "/data/child_name",
                "case_properties": {
                    "child_property_1": "/data/child_property_1"
                },
                "case_type": self.child_type,
                "condition": {
                    "answer": None,
                    "doc_type": "FormActionCondition",
                    "question": None,
                    "type": "always"
                },
                "doc_type": "OpenSubCaseAction",
                "reference_id": None,
                "repeat_context": ""
            })
        )

        child_module = this_app.add_module(
                Module.new_module("Child Module", 'en'))
        child_module = this_app.get_module(1)
        child_module.case_type = self.child_type
        this_app.new_form(
                child_module.id, name="Edit Child", lang='en',
                attachment=read('case_references.xml'))

        this_app.save()
        self.this_app_id = this_app._id

    def tearDown(self):
        self.this_app.delete()

    def test_get_all_case_properties(self):
        # note: this is definitely not full coverage of this method
        self.assertEqual(get_all_case_properties(self.this_app), {
            self.parent_type: [
                'name', 
                'parent_property_1'
            ],
            self.child_type: [
                'child_property_1',
                'name',
                'parent/name',
                'parent/parent_property_1'
            ],
        })

    def test_get_validated_references(self):
        form = self.this_app.get_module(1).get_form(0)
        self.assertEqual(get_validated_references(form), {
            '/data/question1': [
                {
                    'case_type': RefType.PARENT_CASE,
                    'property': 'parent_property_1',
                    'type': RefType.RELEVANT,
                    'valid': True,
                },
                {
                    'case_type': RefType.OWN_CASE,
                    'property': 'child_property_1',
                    'type': RefType.CONSTRAINT,
                    'valid': True,
                },
                {
                    'case_type': RefType.OWN_CASE,
                    'property': 'child_property_1',
                    'type': RefType.CONSTRAINT_ITEXT,
                    'valid': True,
                },
                {
                    'case_type': RefType.OWN_CASE,
                    'property': 'nonexistent_child_property',
                    'type': RefType.LABEL_ITEXT,
                    'valid': False,
                },
                {
                    'case_type': RefType.OWN_CASE,
                    'property': 'child_property_1',
                    'type': RefType.LABEL_ITEXT,
                    'valid': True,
                },
                {
                    'case_type': RefType.PARENT_CASE,
                    'property': 'parent_property_1',
                    'type': RefType.HINT_ITEXT,
                    'valid': True,
                }
            ],
            '/data/question15': [
                {
                    'case_type': RefType.OWN_CASE,
                    'property': 'gender',
                    'type': RefType.REPEAT_COUNT,
                    'valid': False,
                }
            ],
            '/data/question2': [
                {
                    'case_type': RefType.OWN_CASE,
                    'property': 'nonexistent_child_property',
                    'type': RefType.LABEL_ITEXT,
                    'valid': False,
                }
            ],
            '/data/question3': [
                {
                    'case_type': RefType.OWN_CASE,
                    'property': 'child_property_1',
                    'type': RefType.SETVALUE,
                    'valid': True,
                }
            ],
            '/data/datanode': [
                {
                    'case_type': RefType.OWN_CASE,
                    'property': 'nonexistent_child_property',
                    'type': RefType.CALCULATE,
                    'valid': False
                }
            ],

        })
