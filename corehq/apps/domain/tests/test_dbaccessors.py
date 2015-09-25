from django.test import TestCase
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.groups.models import Group
from corehq.apps.users.models import UserRole
from couchforms.models import XFormInstance


class DBAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'domain-domain'

    def test_get_doc_ids_in_domain_by_type(self):
        user_role = UserRole(domain=self.domain)
        group = Group(domain=self.domain)
        xform = XFormInstance(domain=self.domain)
        user_role.save()
        group.save()
        xform.save()
        self.addCleanup(user_role.delete)
        self.addCleanup(group.delete)
        self.addCleanup(xform.delete)
        [doc_id] = get_doc_ids_in_domain_by_type(self.domain, UserRole)
        self.assertEqual(doc_id, user_role.get_id)
