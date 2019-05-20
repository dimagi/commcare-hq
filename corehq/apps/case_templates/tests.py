# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import uuid

from django.test import TestCase

import six

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.case_templates.models import (
    CaseTemplate,
    CaseTemplateInstanceCase,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    run_with_all_backends,
)


class CaseTemplateTests(TestCase):
    def setUp(self):
        super(CaseTemplateTests, self).setUp()
        FormProcessorTestUtils.delete_all_cases()
        FormProcessorTestUtils.delete_all_xforms()

        self.domain = 'template-domain'
        self.factory = CaseFactory(self.domain)
        self.cases = self._create_case_structure()
        self.user_id = six.text_type(uuid.uuid4())

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        FormProcessorTestUtils.delete_all_xforms()
        CaseTemplate.objects.all().delete()
        CaseTemplateInstanceCase.objects.all().delete()
        super(CaseTemplateTests, self).tearDown()

    def _create_case_structure(self):
        self.parent_id = six.text_type(uuid.uuid4())
        self.child_id = six.text_type(uuid.uuid4())
        self.grandchild_id = six.text_type(uuid.uuid4())
        parent = CaseStructure(
            case_id=self.parent_id,
            attrs={
                'case_type': 'parent',
                'update': {'name': 'mother', 'age': '61'},
            },
        )
        child = CaseStructure(
            case_id=self.child_id,
            attrs={
                'case_type': 'child',
                'update': {'name': 'firstborn', 'age': '30'},
            },
            indices=[
                CaseIndex(parent, identifier='parent'),
            ],
        )
        grandchild = CaseStructure(
            case_id=self.grandchild_id,
            attrs={
                'case_type': 'grandchild',
                'update': {'name': 'baby', 'age': '3'},
            },
            indices=[
                CaseIndex(child, identifier='parent'),
            ],
        )
        return self.factory.create_or_update_cases([grandchild])

    @run_with_all_backends
    def test_create_template(self):
        """Creating a template successfully stores the whole tree of cases given a specific root
        """
        template = CaseTemplate.create(self.domain, self.parent_id, 'template', self.user_id)
        template_cases = template.prototype_cases

        self.assertEqual([self.parent_id, self.child_id, self.grandchild_id], template_cases.keys())

        self.assertEqual(template_cases[self.child_id].case_name, 'firstborn')
        self.assertEqual(template_cases[self.child_id].update['age'], '30')
        self.assertEqual(template_cases[self.child_id].index['parent'].case_id, self.parent_id)

        self.assertEqual(template_cases[self.grandchild_id].case_name, 'baby')
        self.assertEqual(template_cases[self.grandchild_id].update['age'], '3')
        self.assertEqual(template_cases[self.grandchild_id].index['parent'].case_id, self.child_id)

    @run_with_all_backends
    def test_create_template_children_only(self):
        """Creating a template successfully stores only the children of the given root
        """
        template = CaseTemplate.create(self.domain, self.child_id, 'template', self.user_id)
        self.assertItemsEqual([self.child_id, self.grandchild_id], template.prototype_cases.keys())

    def test_num_cases(self):
        template = CaseTemplate.create(self.domain, self.parent_id, 'template', self.user_id)
        self.assertEqual(template.num_cases(), 3)

    @run_with_all_backends
    def test_create_instance(self):
        self.assertEqual(len(CaseAccessors(self.domain).get_case_ids_in_domain()), 3)
        template = CaseTemplate.create(self.domain, self.parent_id, 'template', self.user_id)

        suffix = 'cool_new_cases'
        template.create_instance(suffix)

        new_cases = [instance.get_case() for instance in template.instance_cases.all()]

        self.assertEqual(len(CaseAccessors(self.domain).get_case_ids_in_domain()), 6)
        self.assertEqual(len(new_cases), 3)
        self.assertItemsEqual(
            ["{}-{}".format(name, suffix) for name in ['mother', 'firstborn', 'baby']],
            [new_case.name for new_case in new_cases]
        )

    def test_instance_suffix_increments(self):
        """Test that case names increment correctly based on the number of instances created
        """
        template = CaseTemplate.create(self.domain, self.grandchild_id, 'template', self.user_id)
        template.create_instance()
        self.assertEqual(template.instance_cases.last().get_case().name, 'baby-1')

        template.create_instance()
        self.assertEqual(template.instance_cases.last().get_case().name, 'baby-2')

        template.create_instance('un-numbered-suffix')

        template.create_instance()
        self.assertEqual(template.instance_cases.last().get_case().name, 'baby-4')

    @run_with_all_backends
    def test_get_instances(self):
        # Get all the instances created by a template
        original_case_ids = set(CaseAccessors(self.domain).get_case_ids_in_domain())
        template = CaseTemplate.create(self.domain, self.parent_id, 'template', self.user_id)

        new_case_root = template.create_instance()
        new_case_ids = original_case_ids - set(CaseAccessors(self.domain).get_case_ids_in_domain())
        self.assertEqual(
            [case.case_id for case in template.get_instance_cases_for_root(new_case_root)],
            list(new_case_ids),
        )

        second_new_case_root = template.create_instance()
        second_new_case_ids = new_case_ids - set(CaseAccessors(self.domain).get_case_ids_in_domain())
        self.assertEqual(
            [case.case_id for case in template.get_instance_cases_for_root(second_new_case_root)],
            list(second_new_case_ids),
        )

    def test_delete_template(self):
        # Deleting a template deletes all instances and forms against them
        self.assertEqual(len(CaseAccessors(self.domain).get_case_ids_in_domain()), 3)
        self.assertEqual(len(FormAccessors(self.domain).get_all_form_ids_in_domain()), 1)
        template = CaseTemplate.create(self.domain, self.parent_id, 'template', self.user_id)

        template.create_instance()
        self.assertEqual(len(CaseAccessors(self.domain).get_case_ids_in_domain()), 6)
        self.assertEqual(len(FormAccessors(self.domain).get_all_form_ids_in_domain()), 2)

        template.delete()
        self.assertEqual(len(CaseAccessors(self.domain).get_case_ids_in_domain()), 3)
        self.assertEqual(len(FormAccessors(self.domain).get_all_form_ids_in_domain()), 1)


class CaseTemplateInstanceTests(TestCase):

    def test_create_instance_from_template(self):
        # With some arbitrary case XML, create an instance
        # Ensure ownership is the same
        # Ensure all case relationships are the same
        pass

    def test_name_increments(self):
        # With multiple instances, name increments correctly
        pass
