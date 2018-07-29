from __future__ import absolute_import
from __future__ import unicode_literals
import json
import uuid

from django.urls import reverse
from django.test import TestCase
from django.test.utils import override_settings
from mock import patch

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from corehq import toggles
from corehq.apps.cloudcare.api import get_filtered_cases, CaseAPIResult, CASE_STATUS_OPEN, CASE_STATUS_ALL,\
    CASE_STATUS_CLOSED
from corehq.apps.cloudcare.views import ReadableQuestions
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from toggle.shortcuts import update_toggle_cache, clear_toggle_cache
import six

TEST_DOMAIN = "test-cloudcare-domain"


class CaseAPITestMixin(object):
    domain = TEST_DOMAIN
    case_types = ['t1', 't2']
    user_ids = ['TEST_API1', 'TEST_API2']

    @classmethod
    def do_setup(cls):
        cls.project = create_domain(cls.domain)
        cls.password = "****"

        def create_user(username):
            username = format_username(username, cls.domain)
            return CommCareUser.create(cls.domain,
                                       username,
                                       cls.password)

        cls.users = [create_user(id) for id in cls.user_ids]

        def create_case_set(user, child_user):
            # for each user we need one open and one closed case of
            # two different types.
            for type in cls.case_types:
                c1 = _create_case(user, type, close=False) # open
                _create_case(user, type, close=True)       # closed
                # child
                _create_case(child_user,
                             _child_case_type(type), close=False,
                             index={'parent': ('parent-case', c1.case_id)})

        for i, user in enumerate(cls.users):
            create_case_set(user, cls.users[(i + 1) % len(cls.users)])

        cls.test_type = cls.case_types[0]
        cls.test_user_id = cls.users[0]._id

    @classmethod
    def do_teardown(cls):
        for user in cls.users:
            user.delete()
        cls.project.delete()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(TEST_DOMAIN)

    def assertListMatches(self, list, function):
        for item in list:
            self.assertTrue(function(item))

    @property
    def expectedOpenByType(self):
        return len(self.user_ids)

    @property
    def expectedClosedByType(self):
        return len(self.user_ids)

    @property
    def expectedByType(self):
        return self.expectedOpenByType + self.expectedClosedByType

    @property
    def expectedOpenByUser(self):
        return len(self.case_types) * 2 # one per type and child type

    @property
    def expectedClosedByUser(self):
        return len(self.case_types)

    @property
    def expectedByUser(self):
        return self.expectedOpenByUser + self.expectedClosedByUser

    @property
    def expectedOpenByUserWithFootprint(self):
        # each user gets 1 additional child case belonging to their cases
        # for each case type
        return self.expectedOpenByUser + len(self.case_types)

    @property
    def expectedClosedByUserWithFootprint(self):
        # each user gets 1 additional child case belonging to their cases
        return self.expectedClosedByUser

    @property
    def expectedOpen(self):
        return self.expectedOpenByUser * len(self.user_ids)

    @property
    def expectedClosed(self):
        return self.expectedClosedByUser * len(self.user_ids)

    @property
    def expectedAll(self):
        return len(self.user_ids) * len(self.case_types) * 3

    def testGetAllOpen(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_OPEN)
        self.assertEqual(self.expectedOpen, len(list))
        self.assertListMatches(list, lambda c: not c['closed'])

    def testGetAllWithClosed(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL)
        self.assertEqual(self.expectedOpen + self.expectedClosed, len(list))

    def testGetAllOpenWithType(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_OPEN, case_type=self.test_type)
        self.assertEqual(self.expectedOpenByType, len(list))
        self.assertListMatches(list, lambda c: not c['closed'] and c['properties']['case_type'] == self.test_type)

    def testGetAllWithClosedAndType(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, case_type=self.test_type)
        self.assertEqual(self.expectedByType, len(list))
        self.assertListMatches(list, lambda c: c['properties']['case_type'] == self.test_type)

    def testGetOwnedOpen(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_OPEN, footprint=False)
        self.assertEqual(self.expectedOpenByUser, len(list))
        self.assertListMatches(list, lambda c: not c['closed'] and c['user_id'] == self.test_user_id)

    def testGetOwnedClosed(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_CLOSED, footprint=False)
        self.assertEqual(self.expectedClosedByUser, len(list))
        self.assertListMatches(list, lambda c: c['closed'] and c['user_id'] == self.test_user_id)

    def testGetOwnedBoth(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL, footprint=False)
        self.assertEqual(self.expectedByUser, len(list))
        self.assertListMatches(list, lambda c: c['user_id'] == self.test_user_id)

    def testGetOwnedOpenWithFootprint(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_OPEN, footprint=True)
        self.assertEqual(self.expectedOpenByUserWithFootprint, len(list))
        self.assertListMatches(list, lambda c: not c['closed'] or c['user_id'] != self.test_user_id)

    def testGetOwnedClosedWithFootprint(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_CLOSED, footprint=True)
        self.assertEqual(self.expectedClosedByUserWithFootprint, len(list))
        self.assertListMatches(list, lambda c: c['closed'] or c['user_id'] != self.test_user_id)

    def testGetOwnedBothWithFootprint(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL, footprint=True)
        self.assertEqual(self.expectedOpenByUserWithFootprint + self.expectedClosedByUserWithFootprint, len(list))
        # I don't think we can say anything super useful about this base set

    def testGetAllIdsOnly(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, footprint=True,
                                  ids_only=True)
        self.assertEqual(self.expectedAll, len(list))
        self.assertListMatches(list, lambda c: c._couch_doc is None)
        self.assertListMatches(list, lambda c: isinstance(c.to_json(), six.string_types))

    def testFiltersOnAll(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL,
                                  filters={"properties/case_name": _type_to_name(self.test_type)})
        self.assertEqual(self.expectedByType, len(list))
        self.assertListMatches(list, lambda c: c['properties']['case_name'] == _type_to_name(self.test_type))

    def testFiltersOnOwned(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL,
                                  filters={"properties/case_name": _type_to_name(self.test_type)})
        self.assertEqual(2, len(list))
        self.assertListMatches(list, lambda c: c['properties']['case_name'] == _type_to_name(self.test_type))

    def testFiltersWithoutFootprint(self):
        name = _type_to_name(_child_case_type(self.test_type))
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL,
                                  footprint=False,
                                  filters={"properties/case_name": name})
        self.assertEqual(1, len(list))
        self.assertListMatches(list, lambda c: c['properties']['case_name'] == name)

    def testFiltersWithFootprint(self):
        name = _type_to_name(_child_case_type(self.test_type))
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL,
                                  footprint=True,
                                  filters={"properties/case_name": name})
        # when filtering with footprint, the filters get intentionally ignored
        # so just ensure the whole footprint including open and closed is available
        self.assertEqual(self.expectedOpenByUserWithFootprint + self.expectedClosedByUserWithFootprint, len(list))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=False)
class CaseListApiCouchTests(TestCase, CaseAPITestMixin):

    @classmethod
    def setUpClass(cls):
        super(CaseListApiCouchTests, cls).setUpClass()
        cls.do_setup()

    @classmethod
    def tearDownClass(cls):
        cls.do_teardown()
        super(CaseListApiCouchTests, cls).tearDownClass()

    def testGetAllStripHistory(self):
        # strip history doesn't work on SQL domains
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, footprint=True,
                                  strip_history=True)
        self.assertEqual(self.expectedAll, len(list))
        self.assertListMatches(list, lambda c: len(c._couch_doc.actions) == 0)
        self.assertListMatches(list, lambda c: len(c._couch_doc.xform_ids) == 0)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class CaseListApiSQLTests(TestCase, CaseAPITestMixin):
    @classmethod
    def setUpClass(cls):
        super(CaseListApiSQLTests, cls).setUpClass()
        cls.do_setup()

    @classmethod
    def tearDownClass(cls):
        cls.do_teardown()
        super(CaseListApiSQLTests, cls).tearDownClass()


class CaseAPIMiscTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(CaseAPIMiscTests, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.project = create_domain(cls.domain)
        cls.username = uuid.uuid4().hex
        cls.password = "****"

        cls.user = CommCareUser.create(
            cls.domain,
            format_username(cls.username, cls.domain),
            cls.password
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        cls.project.delete()
        super(CaseAPIMiscTests, cls).tearDownClass()

    def testCaseAPIResultJSON(self):
        case = CommCareCase()
        # because of how setattr is overridden you have to set it to None in this wacky way
        case._doc['type'] = None
        case.save()
        self.addCleanup(case.delete)
        self.assertEqual(None, CommCareCase.get(case.case_id).type)
        res_sanitized = CaseAPIResult(domain=TEST_DOMAIN, id=case.case_id, couch_doc=case, sanitize=True)
        res_unsanitized = CaseAPIResult(domain=TEST_DOMAIN, id=case.case_id, couch_doc=case, sanitize=False)

        json = res_sanitized.case_json
        self.assertEqual(json['properties']['case_type'], '')

        json = res_unsanitized.case_json
        self.assertEqual(json['properties']['case_type'], None)


def _child_case_type(type):
    return "%s-child" % type


def _type_to_name(type):
    return "%s-name" % type


def _create_case(user, type, close=False, **extras):
    case_id = uuid.uuid4().hex
    domain = extras.pop('domain', TEST_DOMAIN)
    blocks = [CaseBlock(
        create=True,
        case_id=case_id,
        case_name=_type_to_name(type),
        case_type=type,
        user_id=user.user_id,
        owner_id=user.user_id,
        **extras
    ).as_xml()]
    if close:
        blocks.append(CaseBlock(
            create=False,
            case_id=case_id,
            close=True,
        ).as_xml())
    post_case_blocks(blocks, {'domain': domain})
    case = CaseAccessors(domain).get_case(case_id)
    assert case.closed == close
    return case


class ReadableQuestionsAPITest(TestCase):
    """
    Tests some of the Case API functions
    """
    domain = TEST_DOMAIN

    @classmethod
    def setUpClass(cls):
        super(ReadableQuestionsAPITest, cls).setUpClass()
        cls.project = create_domain(cls.domain)
        cls.password = "****"
        cls.username = format_username('reed', cls.domain)

        cls.user = CommCareUser.create(
            cls.domain,
            cls.username,
            cls.password
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.project.delete()
        super(ReadableQuestionsAPITest, cls).tearDownClass()

    def test_readable_questions(self):
        instanceXml = '''
        <data>
          <question1>ddd</question1>
        </data>
        '''
        self.client.login(username=self.username, password=self.password)
        with patch('corehq.apps.cloudcare.views.readable.get_questions', lambda x, y, z: []):
            result = self.client.post(
                reverse(ReadableQuestions.urlname, args=[self.domain]),
                {
                    'app_id': '123',
                    'xmlns': 'abc',
                    'instanceXml': instanceXml,
                }
            )
        self.assertEqual(result.status_code, 200)
        self.assertIn('form_data', json.loads(result.content))
