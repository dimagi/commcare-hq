from __future__ import absolute_import
import uuid

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.management.commands.restore_domain_membership import (
    user_looks_ok, restore_domain_membership
)
from corehq.apps.users.models import CommCareUser, DomainMembership


class TestRestoreDomainMembership(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestRestoreDomainMembership, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.domain_obj = create_domain(cls.domain)

    def setUp(self):
        self.commcare_user = CommCareUser.create(
            domain=self.domain, username=uuid.uuid4().hex, password='***',
            first_name='Bob'
        )
        self.commcare_user.save()

    def tearDown(self):
        self.commcare_user.delete()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestRestoreDomainMembership, cls).tearDownClass()

    def _reset_domain_membership(self):
        self.commcare_user.domain_membership = DomainMembership(domain=self.domain)
        self.commcare_user.save()
        self.assertFalse(user_looks_ok(self.commcare_user))

    def test_user_looks_ok(self):
        self.assertTrue(user_looks_ok(self.commcare_user))

        # bad
        self.commcare_user.domain_membership = DomainMembership(domain=self.domain)
        self.assertFalse(user_looks_ok(self.commcare_user))

        # good
        self.commcare_user.domain_membership = DomainMembership(domain=self.domain, role_id='123')
        self.assertTrue(user_looks_ok(self.commcare_user))

        # bad
        self.commcare_user.domain_membership = DomainMembership(domain=self.domain)
        self.assertFalse(user_looks_ok(self.commcare_user))

        # good
        del self.commcare_user.user_data['commcare_project']
        self.assertTrue(user_looks_ok(self.commcare_user))

    def test_restore_user(self):
        self._reset_domain_membership()
        self._restore_user()

    def test_restore_user_role(self):
        self.commcare_user.domain_membership.role_id = '123'
        self.commcare_user.save()

        self._reset_domain_membership()

        restored_user = self._restore_user()
        self.assertEqual('123', restored_user.domain_membership.role_id)

    def test_restore_location(self):
        self.commcare_user.location_id = '123'
        self.commcare_user.assigned_location_ids = ['123']
        self.commcare_user.domain_membership.location_id = '123'
        self.commcare_user.domain_membership.assigned_location_ids = ['123']
        self.commcare_user.save()

        self._reset_domain_membership()

        restored_user = self._restore_user()
        self.assertEqual('123', restored_user.domain_membership.location_id)
        self.assertEqual(['123'], restored_user.domain_membership.assigned_location_ids)

    def test_restore_further_back_in_history(self):
        self.commcare_user.last_name = 'Mitchell'
        self.commcare_user.save()

        self._reset_domain_membership()

        restored_user = self._restore_user()
        self.assertEqual('Mitchell', restored_user.last_name)

    def _restore_user(self):
        restore_domain_membership(self.commcare_user)
        user = CommCareUser.get(self.commcare_user._id)
        self.assertTrue(user_looks_ok(user))
        return user
