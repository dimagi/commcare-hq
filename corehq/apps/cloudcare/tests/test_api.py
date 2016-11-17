from mock import patch
import json
import uuid

from django.test import TestCase
from django.core.urlresolvers import reverse
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from toggle.shortcuts import update_toggle_cache, clear_toggle_cache
from corehq import toggles
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.apps.cloudcare.views import ReadableQuestions
from corehq.apps.cloudcare.api import get_filtered_cases, CaseAPIResult, CASE_STATUS_OPEN, CASE_STATUS_ALL,\
    CASE_STATUS_CLOSED

TEST_DOMAIN = "test-cloudcare-domain"


class CaseAPITest(TestCase):
    """
    Tests some of the Case API functions
    """
    domain = TEST_DOMAIN
    case_types = ['t1', 't2']
    user_ids = ['TEST_API1', 'TEST_API2']

    @classmethod
    def setUpClass(cls):
        super(CaseAPITest, cls).setUpClass()
        create_domain(cls.domain)
        cls.password = "****"

        def create_user(username):
            return CommCareUser.create(cls.domain,
                                       format_username(username, cls.domain),
                                       cls.password)

        cls.users = [create_user(id) for id in cls.user_ids]

        update_toggle_cache(toggles.CLOUDCARE_CACHE.slug, TEST_DOMAIN, True, toggles.NAMESPACE_DOMAIN)

    @classmethod
    def tearDownClass(cls):
        for user in cls.users:
            django_user = user.get_django_user()
            django_user.delete()
            user.delete()
        clear_toggle_cache(toggles.CLOUDCARE_CACHE.slug, TEST_DOMAIN, toggles.NAMESPACE_DOMAIN)
        super(CaseAPITest, cls).tearDownClass()

    def setUp(self):
        super(CaseAPITest, self).setUp()

        def create_case_set(user, child_user):
            # for each user we need one open and one closed case of
            # two different types.
            for type in self.case_types:
                c1 = _create_case(user, type, close=False) # open
                _create_case(user, type, close=True)       # closed
                # child
                _create_case(child_user,
                             _child_case_type(type), close=False,
                             index={'parent': ('parent-case', c1.case_id)})

        for i, user in enumerate(self.users):
            create_case_set(user, self.users[(i + 1) % len(self.users)])

        self.test_type = self.case_types[0]
        self.test_user_id = self.users[0]._id

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(TEST_DOMAIN)
        super(CaseAPITest, self).tearDown()

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

    @run_with_all_backends
    def testGetAllOpen(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_OPEN)
        self.assertEqual(self.expectedOpen, len(list))
        self.assertListMatches(list, lambda c: not c['closed'])

    @run_with_all_backends
    def testGetAllWithClosed(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL)
        self.assertEqual(self.expectedOpen + self.expectedClosed, len(list))

    @run_with_all_backends
    def testGetAllOpenWithType(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_OPEN, case_type=self.test_type)
        self.assertEqual(self.expectedOpenByType, len(list))
        self.assertListMatches(list, lambda c: not c['closed'] and c['properties']['case_type'] == self.test_type)

    @run_with_all_backends
    def testGetAllWithClosedAndType(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, case_type=self.test_type)
        self.assertEqual(self.expectedByType, len(list))
        self.assertListMatches(list, lambda c: c['properties']['case_type'] == self.test_type)

    @run_with_all_backends
    def testGetOwnedOpen(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_OPEN, footprint=False)
        self.assertEqual(self.expectedOpenByUser, len(list))
        self.assertListMatches(list, lambda c: not c['closed'] and c['user_id'] == self.test_user_id)

    @run_with_all_backends
    def testGetOwnedClosed(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_CLOSED, footprint=False)
        self.assertEqual(self.expectedClosedByUser, len(list))
        self.assertListMatches(list, lambda c: c['closed'] and c['user_id'] == self.test_user_id)

    @run_with_all_backends
    def testGetOwnedBoth(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL, footprint=False)
        self.assertEqual(self.expectedByUser, len(list))
        self.assertListMatches(list, lambda c: c['user_id'] == self.test_user_id)

    @run_with_all_backends
    def testGetOwnedOpenWithFootprint(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_OPEN, footprint=True)
        self.assertEqual(self.expectedOpenByUserWithFootprint, len(list))
        self.assertListMatches(list, lambda c: not c['closed'] or c['user_id'] != self.test_user_id)

    @run_with_all_backends
    def testGetOwnedClosedWithFootprint(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_CLOSED, footprint=True)
        self.assertEqual(self.expectedClosedByUserWithFootprint, len(list))
        self.assertListMatches(list, lambda c: c['closed'] or c['user_id'] != self.test_user_id)

    @run_with_all_backends
    def testGetOwnedBothWithFootprint(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL, footprint=True)
        self.assertEqual(self.expectedOpenByUserWithFootprint + self.expectedClosedByUserWithFootprint, len(list))
        # I don't think we can say anything super useful about this base set

    def testGetAllStripHistory(self):
        # strip history doesn't work on SQL domains
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, footprint=True,
                                  strip_history=True)
        self.assertEqual(self.expectedAll, len(list))
        self.assertListMatches(list, lambda c: len(c._couch_doc.actions) == 0)
        self.assertListMatches(list, lambda c: len(c._couch_doc.xform_ids) == 0)

    @run_with_all_backends
    def testGetAllIdsOnly(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, footprint=True,
                                  ids_only=True)
        self.assertEqual(self.expectedAll, len(list))
        self.assertListMatches(list, lambda c: c._couch_doc is None)
        self.assertListMatches(list, lambda c: isinstance(c.to_json(), basestring))

    @run_with_all_backends
    def testFiltersOnAll(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL,
                                  filters={"properties/case_name": _type_to_name(self.test_type)})
        self.assertEqual(self.expectedByType, len(list))
        self.assertListMatches(list, lambda c: c['properties']['case_name'] == _type_to_name(self.test_type))

    @run_with_all_backends
    def testFiltersOnOwned(self):
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL,
                                  filters={"properties/case_name": _type_to_name(self.test_type)})
        self.assertEqual(2, len(list))
        self.assertListMatches(list, lambda c: c['properties']['case_name'] == _type_to_name(self.test_type))

    @run_with_all_backends
    def testFiltersWithoutFootprint(self):
        name = _type_to_name(_child_case_type(self.test_type))
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL,
                                  footprint=False,
                                  filters={"properties/case_name": name})
        self.assertEqual(1, len(list))
        self.assertListMatches(list, lambda c: c['properties']['case_name'] == name)

    @run_with_all_backends
    def testFiltersWithFootprint(self):
        name = _type_to_name(_child_case_type(self.test_type))
        list = get_filtered_cases(self.domain, user_id=self.test_user_id, status=CASE_STATUS_ALL,
                                  footprint=True,
                                  filters={"properties/case_name": name})
        # when filtering with footprint, the filters get intentionally ignored
        # so just ensure the whole footprint including open and closed is available
        self.assertEqual(self.expectedOpenByUserWithFootprint + self.expectedClosedByUserWithFootprint, len(list))

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

    def testGetCasesCaching(self):
        user = self.users[0]

        self.client.login(username=user.username, password=self.password)
        result = self.client.get(reverse('cloudcare_get_cases', args=[self.domain]), {
            'ids_only': 'true',
            'use_cache': 'true',
        })
        cases = json.loads(result.content)
        self.assertEqual(result.status_code, 200)

        _create_case(user, self.case_types[0], close=False)

        result = self.client.get(reverse('cloudcare_get_cases', args=[self.domain]), {
            'ids_only': 'true',
            'use_cache': 'true',
        })
        cases_cached = json.loads(result.content)
        self.assertEqual(len(cases), len(cases_cached))

        result = self.client.get(reverse('cloudcare_get_cases', args=[self.domain]), {
            'ids_only': 'true',
            'use_cache': 'false',
        })
        cases_not_cached = json.loads(result.content)
        self.assertEqual(len(cases) + 1, len(cases_not_cached))

    def testGetCasesNoCaching(self):
        """
        Tests get_cases when it shouldn't cache. E.g. when ids_only is false or cache is false
        """
        user = self.users[0]

        self.client.login(username=user.username, password=self.password)
        result = self.client.get(reverse('cloudcare_get_cases', args=[self.domain]), {
            'ids_only': 'false',
            'use_cache': 'true',
        })
        cases = json.loads(result.content)
        self.assertEqual(result.status_code, 200)
        _create_case(user, self.case_types[0], close=False)

        result = self.client.get(reverse('cloudcare_get_cases', args=[self.domain]), {
            'ids_only': 'false',
            'use_cache': 'true',
        })
        cases_not_cached = json.loads(result.content)
        self.assertEqual(len(cases) + 1, len(cases_not_cached))


def _child_case_type(type):
    return "%s-child" % type


def _type_to_name(type):
    return "%s-name" % type


def _create_case(user, type, close=False, **extras):
    case_id = uuid.uuid4().hex
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
    post_case_blocks(blocks, {'domain': TEST_DOMAIN})
    case = CaseAccessors(TEST_DOMAIN).get_case(case_id)
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
        super(ReadableQuestionsAPITest, cls).tearDownClass()
        cls.user.delete()
        cls.project.delete()

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
