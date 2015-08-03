import json
import uuid

from django.test import TestCase
from django.core.urlresolvers import reverse
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import delete_all_cases
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from casexml.apps.phone.xml import date_to_xml_string
from toggle.shortcuts import update_toggle_cache, clear_toggle_cache
from corehq import toggles
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
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

    def setUp(self):
        create_domain(self.domain)
        self.password = "****"

        def create_user(username):
            return CommCareUser.create(self.domain,
                                       format_username(username, self.domain),
                                       self.password)

        self.users = [create_user(id) for id in self.user_ids]

        def create_case_set(user, child_user):
            # for each user we need one open and one closed case of
            # two different types.
            for type in self.case_types:
                c1 = _create_case(user, type, close=False) # open
                _create_case(user, type, close=True)       # closed
                # child
                _create_case(child_user,
                             _child_case_type(type), close=False,
                             index={'parent': ('parent-case', c1._id)})

        for i, user in enumerate(self.users):
            create_case_set(user, self.users[(i + 1) % len(self.users)])

        self.test_type = self.case_types[0]
        self.test_user_id = self.users[0]._id
        update_toggle_cache(toggles.CLOUDCARE_CACHE.slug, TEST_DOMAIN, True, toggles.NAMESPACE_DOMAIN)

    def tearDown(self):
        for user in self.users:
            django_user = user.get_django_user()
            django_user.delete()
            user.delete()
        delete_all_cases()
        clear_toggle_cache(toggles.CLOUDCARE_CACHE.slug, TEST_DOMAIN, toggles.NAMESPACE_DOMAIN)

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

    def testGetAllStripHistory(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, footprint=True,
                                  strip_history=True)
        self.assertEqual(self.expectedAll, len(list))
        self.assertListMatches(list, lambda c: len(c._couch_doc.actions) == 0)
        self.assertListMatches(list, lambda c: len(c._couch_doc.xform_ids) == 0)

    def testGetAllIdsOnly(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, footprint=True,
                                  ids_only=True)
        self.assertEqual(self.expectedAll, len(list))
        self.assertListMatches(list, lambda c: isinstance(c._couch_doc, dict))
        self.assertListMatches(list, lambda c: isinstance(c.to_json(), basestring))

    def testGetAllIdsOnlyStripHistory(self):
        list = get_filtered_cases(self.domain, status=CASE_STATUS_ALL, footprint=True,
                                  ids_only=True, strip_history=True)
        self.assertEqual(self.expectedAll, len(list))
        self.assertListMatches(list, lambda c: isinstance(c._couch_doc, dict))
        self.assertListMatches(list, lambda c: 'actions' not in c._couch_doc)
        self.assertListMatches(list, lambda c: 'xform_ids' not in c._couch_doc)
        self.assertListMatches(list, lambda c: isinstance(c.to_json(), basestring))

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

    def testCaseAPIResultJSON(self):
        try:
            case = CommCareCase()
            # because of how setattr is overridden you have to set it to None in this wacky way
            case._doc['type'] = None
            case.save()
            self.assertEqual(None, CommCareCase.get(case._id).type)
            res_sanitized = CaseAPIResult(id=case._id, couch_doc=case, sanitize=True)
            res_unsanitized = CaseAPIResult(id=case._id, couch_doc=case, sanitize=False)

            json = res_sanitized.case_json
            self.assertEqual(json['properties']['case_type'], '')

            json = res_unsanitized.case_json
            self.assertEqual(json['properties']['case_type'], None)
        finally:
            case.delete()

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
        version=V2,
        **extras
    ).as_xml(format_datetime=date_to_xml_string)]
    if close:
        blocks.append(CaseBlock(
            create=False,
            case_id=case_id,
            close=True,
            version=V2,
        ).as_xml(format_datetime=date_to_xml_string))
    post_case_blocks(blocks, {'domain': TEST_DOMAIN})
    case = CommCareCase.get(case_id)
    assert case.closed == close
    return case
