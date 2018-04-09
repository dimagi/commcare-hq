from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.casegroups.dbaccessors import get_case_groups_in_domain, \
    get_number_of_case_groups_in_domain, get_case_group_meta_in_domain
from corehq.apps.casegroups.models import CommCareCaseGroup


class DBAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
        cls.domain = 'case-group-test'
        cls.case_groups = [
            CommCareCaseGroup(name='A', domain=cls.domain, cases=['A', 'B']),
            CommCareCaseGroup(name='b', domain=cls.domain, cases=['B', 'C']),
            CommCareCaseGroup(name='C', domain=cls.domain, cases=['A', 'D']),
            CommCareCaseGroup(name='D', domain=cls.domain, cases=['B', 'C']),
            CommCareCaseGroup(name='E', domain=cls.domain + 'x', cases=['B', 'C']),
        ]
        for group in cls.case_groups:
            # Clear cache and save
            group.save()

    @classmethod
    def tearDownClass(cls):
        for group in cls.case_groups:
            # Clear cache and delete
            group.delete()
        super(DBAccessorsTest, cls).tearDownClass()

    def get_ids(self, groups):
        return [group.get_id for group in groups]

    def test_get_case_groups_in_domain(self):
        # Test that the result should be ordered by name
        self.assertEqual(
            self.get_ids(get_case_groups_in_domain(self.domain)),
            self.get_ids(self.case_groups[0:4]),
        )

    def test_get_number_of_case_groups_in_domain(self):
        self.assertEqual(get_number_of_case_groups_in_domain(self.domain), 4)

    def test_get_case_group_meta_in_domain(self):
        self.assertEqual(
            get_case_group_meta_in_domain(self.domain),
            [(group.get_id, group.name) for group in self.case_groups[0:4]],
        )
