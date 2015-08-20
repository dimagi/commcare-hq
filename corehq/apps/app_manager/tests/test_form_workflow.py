import copy
from django.test import SimpleTestCase
from mock import patch
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import WORKFLOW_FORM, FormLink, AdvancedOpenCaseAction, OpenCaseAction, \
    AdvancedModule, Application, Module, UpdateCaseAction, LoadUpdateAction, OpenSubCaseAction, FormActionCondition, \
    WORKFLOW_MODULE, WORKFLOW_ROOT
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.builds.models import BuildSpec
from corehq.feature_previews import MODULE_FILTER
from corehq.toggles import NAMESPACE_DOMAIN
from toggle.shortcuts import update_toggle_cache, clear_toggle_cache


class TestFormWorkflow(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'form_workflow')
    default_spec = {
        "m": [
            {
                "name": "m0",
                "type": "basic",
                "f": [
                    {"name": "m0f0", "actions": ["open"]}
                ]
            },
            {
                "name": "m1",
                "type": "basic",
                "f": [
                    {"name": "m1f0", "actions": ["update"]}
                ]
            }
        ]
    }

    def setUp(self):
        update_toggle_cache(MODULE_FILTER.slug, 'domain', True, NAMESPACE_DOMAIN)
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_patch.start()

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()
        clear_toggle_cache(MODULE_FILTER.slug, 'domain', NAMESPACE_DOMAIN)

    def make_app(self, spec):
        """
        {
            "m": [
                {
                    "name": "m0",  # also the module ID
                    "type": "basic / advanced",
                    "case_type": "foo",  # defaults to 'frog',
                    "parent": "m1",  # name / ID of parent module
                    "f": [
                        {
                            "name": "m0f0",
                            "actions": {
                                "action": "open / update / open_subcase",
                                "case_type": "foo"  # only applicable to advanced modules
                                "parent": "{open / update}_{case_type}"  # only applicable to advanced modules
                        }
                    ]
                },
            ]
        }
        """
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)
        app.build_spec = BuildSpec.from_string('2.9.0/latest')
        case_type = "frog"
        for m_spec in spec["m"]:
            m_type = m_spec['type']
            m_class = Module if m_type == 'basic' else AdvancedModule
            module = app.add_module(m_class.new_module(m_spec['name'], None))
            module.unique_id = m_spec['name']
            module.case_type = m_spec.get("case_type", "frog")
            module.root_module_id = m_spec.get("parent", None)
            for f_spec in m_spec['f']:
                form_name = f_spec["name"]
                form = app.new_form(module.id, form_name, None)
                form.unique_id = form_name
                for a_spec in f_spec.get('actions', []):
                    if isinstance(a_spec, dict):
                        action = a_spec['action']
                        case_type = a_spec.get("case_type", case_type)
                        parent = a_spec.get("parent", None)
                    else:
                        action = a_spec
                    if 'open' == action:
                        if m_type == "basic":
                            form.actions.open_case = OpenCaseAction(name_path="/data/question1")
                            form.actions.open_case.condition.type = 'always'
                        else:
                            form.actions.open_cases.append(AdvancedOpenCaseAction(
                                case_type=case_type,
                                case_tag='open_{}'.format(case_type),
                                name_path='/data/name'
                            ))
                    elif 'update' == action:
                        if m_type == "basic":
                            form.requires = 'case'
                            form.actions.update_case = UpdateCaseAction(update={'question1': '/data/question1'})
                            form.actions.update_case.condition.type = 'always'
                        else:
                            form.actions.load_update_cases.append(LoadUpdateAction(
                                case_type=case_type,
                                case_tag='update_{}'.format(case_type),
                                parent_tag=parent,
                            ))
                    elif 'open_subacse':
                        if m_type == "basic":
                            form.actions.subcases.append(OpenSubCaseAction(
                                case_type=case_type,
                                case_name="/data/question1",
                                condition=FormActionCondition(type='always')
                            ))
                        else:
                            form.actions.open_cases.append(AdvancedOpenCaseAction(
                                case_type=case_type,
                                case_tag='subcase_{}'.format(case_type),
                                name_path='/data/name',
                                parent_tag=parent
                            ))

        return app

    def test_basic(self):
        spec = copy.deepcopy(self.default_spec)
        spec["m"][0]["f"][0]["actions"] = []
        spec["m"][1]["f"][0]["actions"] = []
        app = self.make_app(spec)

        m0f0 = app.get_form("m0f0")
        m1f0 = app.get_form("m1f0")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) &lt; 7", form_id=m1f0.unique_id)
        ]
        self.assertXmlPartialEqual(self.get_xml('form_link_basic'), app.create_suite(), "./entry[1]")

    def test_with_case_management_both_update(self):
        spec = copy.deepcopy(self.default_spec)
        spec["m"][0]["f"][0]["actions"] = ["update"]
        app = self.make_app(spec)

        m0f0 = app.get_form("m0f0")
        m1f0 = app.get_form("m1f0")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="(today() - dob) > 7", form_id=m1f0.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_update_case'), app.create_suite(), "./entry[1]")

    def test_with_case_management_create_update(self):
        app = self.make_app(self.default_spec)

        m0f0 = app.get_form("m0f0")
        m1f0 = app.get_form("m1f0")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath='true()', form_id=m1f0.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_create_update_case'), app.create_suite(), "./entry[1]")

    def test_with_case_management_multiple_links(self):
        spec = copy.deepcopy(self.default_spec)
        spec["m"][1]["f"].append({"name": "m1f1", "actions": ["open"]})
        app = self.make_app(spec)

        m0f0 = app.get_form("m0f0")
        m1f0 = app.get_form("m1f0")
        m1f1 = app.get_form("m1f1")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="a = 1", form_id=m1f0.unique_id),
            FormLink(xpath="a = 2", form_id=m1f1.unique_id)
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_multiple'), app.create_suite(), "./entry[1]")

    def test_link_to_child_module(self):
        spec = {
            "m": [
                {
                    "name": "enroll child",
                    "type": "basic",
                    "case_type": "child",
                    "f": [
                        {"name": "enroll child", "actions": ["open"]}
                    ]
                },
                {
                    "name": "child visit module",
                    "type": "basic",
                    "case_type": "child",
                    "f": [
                        {"name": "followup", "actions": [
                            "update",
                            {"action": "open_subcase", "case_type": "visit"}
                        ]}
                    ]
                },
                {
                    "name": "visit history",
                    "type": "advanced",
                    "case_type": "visit",
                    "parent": "child visit module",
                    "f": [
                        {"name": "treatment", "actions": [
                            {"action": "update", "case_type": "child"},
                            {"action": "update", "case_type": "visit", "parent": "update_child"}
                        ]}
                    ]
                }
            ]
        }
        app = self.make_app(spec)

        m0f0 = app.get_form("enroll child")
        m1f0 = app.get_form("followup")
        m2f0 = app.get_form("treatment")

        m0f0.post_form_workflow = WORKFLOW_FORM
        m0f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id),
        ]

        m1f0.post_form_workflow = WORKFLOW_FORM
        m1f0.form_links = [
            FormLink(xpath="true()", form_id=m2f0.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_tdh'), app.create_suite(), "./entry")

    def test_link_to_form_in_parent_module(self):
        spec = {
            "m": [
                {
                    "name": "enroll child",
                    "type": "basic",
                    "case_type": "child",
                    "f": [
                        {"name": "enroll child", "actions": ["open"]}
                    ]
                },
                {
                    "name": "child visit module",
                    "type": "basic",
                    "case_type": "child",
                    "f": [
                        {"name": "edit child", "actions": [
                            "update",
                        ]}
                    ]
                },
                {
                    "name": "visit history",
                    "type": "advanced",
                    "case_type": "visit",
                    "parent": "child visit module",
                    "f": [
                        {"name": "link to child", "actions": [
                            {"action": "update", "case_type": "child"},
                        ]}
                    ]
                }
            ]
        }
        app = self.make_app(spec)

        m1f1 = app.get_form("edit child")
        m2f1 = app.get_form("link to child")

        # link to child -> edit child
        m2f1.post_form_workflow = WORKFLOW_FORM
        m2f1.form_links = [
            FormLink(xpath="true()", form_id=m1f1.unique_id),
        ]

        self.assertXmlPartialEqual(self.get_xml('form_link_child_modules'), app.create_suite(), "./entry[3]")

    def test_form_workflow_previous(self):
        """
        m0 - basic module - no case
            f0 - no case management
            f1 - no case management
        m1 - basic module - patient case
            f0 - register case
            f1 - update case
        m2 - basic module - patient case
            f0 - update case
            f1 - update case
        m3 - basic module - child case
            f0 - update child case
            f1 - update child case
        m4 - advanced module - patient case
            f0 - load a -> b
            f1 - load a -> b -> c
            f2 - load a -> b -> autoselect
        """
        app = Application.wrap(self.get_json('suite-workflow'))
        self.assertXmlPartialEqual(self.get_xml('suite-workflow-previous'), app.create_suite(), "./entry")

    def test_form_workflow_module(self):
        app = Application.wrap(self.get_json('suite-workflow'))
        for module in app.get_modules():
            for form in module.get_forms():
                form.post_form_workflow = WORKFLOW_MODULE

        self.assertXmlPartialEqual(self.get_xml('suite-workflow-module'), app.create_suite(), "./entry")

    def test_form_workflow_module_in_root(self):
        app = Application.wrap(self.get_json('suite-workflow'))
        for m in [1, 2]:
            module = app.get_module(m)
            module.put_in_root = True

        self.assertXmlPartialEqual(self.get_xml('suite-workflow-module-in-root'), app.create_suite(), "./entry")

    def test_form_workflow_root(self):
        app = Application.wrap(self.get_json('suite-workflow'))
        for module in app.get_modules():
            for form in module.get_forms():
                form.post_form_workflow = WORKFLOW_ROOT

        self.assertXmlPartialEqual(self.get_xml('suite-workflow-root'), app.create_suite(), "./entry")
