import re
from uuid import uuid4

from django.core.urlresolvers import reverse
from django.test import TestCase, Client
from mock import patch

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.case_search.models import CLAIM_CASE_TYPE, CaseSearchConfig, SEARCH_QUERY_ADDITION_KEY, \
    CaseSearchQueryAddition
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import conditionally_run_with_all_backends
from corehq.pillows.case_search import get_case_search_reindexer
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO, CASE_SEARCH_INDEX
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping

DOMAIN = 'test-domain'
USERNAME = 'testy_mctestface'
PASSWORD = '123'
CASE_NAME = 'Jamie Hand'
CASE_TYPE = 'case'
OWNER_ID = 'nerc'
TIMESTAMP = '2016-04-17T10:13:06.588694Z'
FIXED_DATESTAMP = '2016-04-17'
PATTERN = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z'
DATE_PATTERN = r'\d{4}-\d{2}-\d{2}'

# cf. http://www.theguardian.com/environment/2016/apr/17/boaty-mcboatface-wins-poll-to-name-polar-research-vessel


class CaseClaimEndpointTests(TestCase):
    def setUp(self):
        self.domain = create_domain(DOMAIN)
        self.user = CommCareUser.create(DOMAIN, USERNAME, PASSWORD)
        initialize_index_and_mapping(get_es_new(), CASE_SEARCH_INDEX_INFO)
        CaseSearchConfig.objects.get_or_create(pk=DOMAIN, enabled=True)
        delete_all_cases()
        self.case_id = uuid4().hex
        _, [self.case] = post_case_blocks([CaseBlock(
            create=True,
            case_id=self.case_id,
            case_type=CASE_TYPE,
            case_name=CASE_NAME,
            external_id=CASE_NAME,
            user_id=OWNER_ID,
            owner_id=OWNER_ID,
            update={'opened_by': OWNER_ID},
        ).as_xml()], {'domain': DOMAIN})
        get_case_search_reindexer(DOMAIN).reindex()
        es = get_es_new()
        es.indices.refresh(CASE_SEARCH_INDEX)

    def tearDown(self):
        ensure_index_deleted(CASE_SEARCH_INDEX)
        self.user.delete()
        self.domain.delete()
        for query_addition in CaseSearchQueryAddition.objects.all():
            query_addition.delete()

    @conditionally_run_with_all_backends
    def test_claim_case(self):
        """
        A claim case request should create an extension case
        """
        self.assertEqual(len(CaseAccessors(DOMAIN).get_case_ids_in_domain(CLAIM_CASE_TYPE)), 0)

        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        url = reverse('claim_case', kwargs={'domain': DOMAIN})
        client.post(url, {'case_id': self.case_id})

        claim_ids = CaseAccessors(DOMAIN).get_case_ids_in_domain(CLAIM_CASE_TYPE)
        self.assertEqual(len(claim_ids), 1)
        claim = CaseAccessors(DOMAIN).get_case(claim_ids[0])
        self.assertEqual(claim.owner_id, self.user.get_id)
        self.assertEqual(claim.name, CASE_NAME)

    @conditionally_run_with_all_backends
    def test_duplicate_client_claim(self):
        """
        Server should not allow the same client to claim the same case more than once
        """
        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        url = reverse('claim_case', kwargs={'domain': DOMAIN})
        # First claim
        response = client.post(url, {'case_id': self.case_id})
        self.assertEqual(response.status_code, 200)
        # Dup claim
        response = client.post(url, {'case_id': self.case_id})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.content, 'You have already claimed that case')

    @conditionally_run_with_all_backends
    def test_duplicate_user_claim(self):
        """
        Server should not allow the same user to claim the same case more than once
        """
        client1 = Client()
        client1.login(username=USERNAME, password=PASSWORD)
        url = reverse('claim_case', kwargs={'domain': DOMAIN})
        # First claim
        response = client1.post(url, {'case_id': self.case_id})
        self.assertEqual(response.status_code, 200)
        # Dup claim
        client2 = Client()
        client2.login(username=USERNAME, password=PASSWORD)
        response = client2.post(url, {'case_id': self.case_id})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.content, 'You have already claimed that case')

    @conditionally_run_with_all_backends
    def test_search_endpoint(self):
        known_result = (
            '<results id="case">'  # ("case" is not the case type)
            '<case case_id="{case_id}" '
            'case_type="{case_type}" '
            'owner_id="{owner_id}" '
            'status="open">'
            '<case_name>{case_name}</case_name>'
            '<last_modified>2016-04-17T10:13:06.588694Z</last_modified>'
            '<external_id>Jamie Hand</external_id>'
            '<date_opened>2016-04-17</date_opened>'
            '<location_id>None</location_id>'
            '<referrals>None</referrals>'
            '</case>'
            '</results>'.format(
                case_id=self.case_id,
                case_name=CASE_NAME,
                case_type=CASE_TYPE,
                owner_id=OWNER_ID,
            ))

        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        url = reverse('remote_search', kwargs={'domain': DOMAIN})
        response = client.get(url, {'name': 'Jamie Hand', 'case_type': CASE_TYPE})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(re.sub(DATE_PATTERN, FIXED_DATESTAMP, re.sub(PATTERN, TIMESTAMP, response.content)), known_result)

    @patch('corehq.apps.es.es_query.run_query')
    def test_search_query_addition(self, run_query_mock):
        new_must_clause = {
            "bool": {
                "should": [
                    {
                        "nested": {
                            "path": "case_properties",
                            "query": {
                                "filtered": {
                                    "filter": {
                                        "term": {"case_properties.key": "is_inactive"}
                                    },
                                    "query": {
                                        "match": {
                                            "case_properties.value": {
                                                "fuzziness": "0", "query": "yes"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    {
                        "nested": {
                            "path": "case_properties",
                            "query": {
                                "filtered": {
                                    "filter": {
                                        "term": {"case_properties.key": "awaiting_claim"}
                                    },
                                    "query": {
                                        "match": {
                                            "case_properties.value": {
                                                "fuzziness": "0", "query": "yes"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        }

        query_partial = {
            "bool": {
                "must": [
                    new_must_clause
                ]
            }
        }

        query_addition = CaseSearchQueryAddition(domain=DOMAIN, name="foo", query_addition=query_partial)
        query_addition.save()

        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        url = reverse('remote_search', kwargs={'domain': DOMAIN})
        some_case_name = "wut"
        response = client.get(
            url,
            {'name': some_case_name, 'case_type': CASE_TYPE, SEARCH_QUERY_ADDITION_KEY: query_addition.id}
        )

        self.assertEqual(response.status_code, 200)

        expected_query = {
            'query': {
                'filtered': {
                    'filter': {
                        'and': [
                            {'term': {'domain.exact': DOMAIN}},
                            {'term': {'type.exact': CASE_TYPE}},
                            {'term': {'closed': False}},
                            {'match_all': {}}
                        ]
                    },
                    'query': {
                        'bool': {
                            'must': [
                                {
                                    'nested': {
                                        'path': 'case_properties',
                                        'query': {
                                            'filtered': {
                                                'filter': {'term': {'case_properties.key': u'name'}},
                                                'query': {
                                                    'match': {
                                                        'case_properties.value': {
                                                            'query': some_case_name, 'fuzziness': '0'
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                },
                                new_must_clause
                            ]
                        }
                    }
                }
            },
            'size': 10
        }
        run_query_mock.assert_called_with("case_search", expected_query, debug_host=None)
