import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.locations.models import make_location, LocationType
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.util import format_username
from couchforms.models import XFormInstance


class TestDocInfo(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.domain_obj = create_domain(cls.domain)

    def test_couch_user(self):
        user = CommCareUser.create(self.domain, format_username("lilly", self.domain), "123", None, None)
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        self._test_doc(user.user_id, "CommCareUser")

    def test_web_user(self):
        user = WebUser.create(self.domain, "marias@email.com", "123", None, None)
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        self._test_doc(user.user_id, "WebUser")

    def test_location(self):
        loc_type = LocationType(domain=self.domain, name='type')
        loc_type.save()
        self.addCleanup(loc_type.delete)
        location = make_location(
            domain=self.domain,
            site_code='doc_info_test',
            name='doc_info_test',
            location_type='type'
        )
        location.save()
        self.addCleanup(location.delete)
        self._test_doc(location.location_id, "Location")

    def test_group(self):
        group = Group(domain=self.domain, name='doc_info_test')
        group.save()
        self.addCleanup(group.delete)
        self._test_doc(group.get_id, "Group")

    def test_case_group(self):
        group = CommCareCaseGroup(name='A', domain=self.domain, cases=['A', 'B'])
        group.save()
        self.addCleanup(group.delete)
        self._test_doc(group.get_id, "CommCareCaseGroup")

    def test_couch_case(self):
        case = CommCareCase(domain=self.domain)
        case.save()
        self.addCleanup(case.delete)
        self._test_doc(case.get_id, "CommCareCase")

    def test_sql_case(self):
        case, xform = self._make_form_and_case()
        self._test_doc(case.case_id, "CommCareCase")

    def test_couch_form(self):
        form = XFormInstance(
            xmlns='doc_info_test',
            domain=self.domain,
        )
        form.save()
        self.addCleanup(form.delete)
        self._test_doc(form.form_id, "XFormInstance")

    def test_sql_form(self):
        case, xform = self._make_form_and_case()
        self._test_doc(xform.form_id, "XFormInstance")

    def _make_form_and_case(self):
        xform, cases = submit_case_blocks([CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='doc_info_test',
            case_name='doc_info_test',
            owner_id='doc_info_test',
            create=True,
        ).as_text()], domain=self.domain)
        case = cases[0]
        self.addCleanup(case.delete)
        self.addCleanup(xform.delete)
        return case, xform

    def _test_doc(self, doc_id, doc_type):
        info = get_doc_info_by_id(self.domain, doc_id)
        self.assertEqual(info.id, doc_id)
        self.assertEqual(info.domain, self.domain)
        self.assertEqual(info.type, doc_type)
        self.assertFalse(info.is_deleted)
        return info
