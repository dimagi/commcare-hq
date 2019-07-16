from __future__ import absolute_import
from __future__ import unicode_literals
import re
from collections import OrderedDict
from flaky import flaky
from uuid import uuid4

from django.urls import reverse
from django.test import TestCase, Client
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from mock import patch

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.case_search.models import (
    CLAIM_CASE_TYPE,
    CaseSearchConfig,
    SEARCH_QUERY_ADDITION_KEY,
    CaseSearchQueryAddition,
    IgnorePatterns,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new, ES_DEFAULT_INSTANCE
from corehq.apps.es.tests.utils import ElasticTestMixin
from corehq.apps.case_search.utils import CaseSearchCriteria
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.pillows.case_search import CaseSearchReindexerFactory
from corehq.pillows.mappings.case_search_mapping import (
    CASE_SEARCH_INDEX_INFO,
    CASE_SEARCH_INDEX,
    CASE_SEARCH_MAX_RESULTS,
)
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping

DOMAIN = 'swashbucklers'
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


class CaseSearchTests(TestCase, ElasticTestMixin):
    def setUp(self):
        super(CaseSearchTests, self).setUp()
        self.config, created = CaseSearchConfig.objects.get_or_create(pk=DOMAIN, enabled=True)

    def test_add_blacklisted_ids(self):
        criteria = {
            "commcare_blacklisted_owner_ids": "id1 id2 id3,id4"
        }
        expected = {'query':
                    {'filtered':
                     {'filter':
                      {'and': [
                          {'term': {'domain.exact': 'swashbucklers'}},
                          {"term": {"type.exact": "case_type"}},
                          {"term": {"closed": False}},
                          {'not': {'term': {'owner_id': 'id1'}}},
                          {'not': {'term': {'owner_id': 'id2'}}},
                          {'not': {'term': {'owner_id': 'id3,id4'}}},
                          {'match_all': {}}
                      ]},
                      "query": {
                          "match_all": {}
                      }}},
                    'size': CASE_SEARCH_MAX_RESULTS}

        self.checkQuery(
            CaseSearchCriteria(DOMAIN, 'case_type', criteria).search_es,
            expected
        )

    def test_add_ignore_pattern_queries(self):
        rc = IgnorePatterns(
            domain=DOMAIN,
            case_type='case_type',
            case_property='name',
            regex=' word',
        )                       # remove ' word' from the name case property
        rc.save()
        self.config.ignore_patterns.add(rc)
        rc = IgnorePatterns(
            domain=DOMAIN,
            case_type='case_type',
            case_property='name',
            regex=' gone',
        )                       # remove ' gone' from the name case property
        rc.save()
        self.config.ignore_patterns.add(rc)
        rc = IgnorePatterns(
            domain=DOMAIN,
            case_type='case_type',
            case_property='special_id',
            regex='-',
        )                       # remove '-' from the special id case property
        rc.save()
        self.config.ignore_patterns.add(rc)
        self.config.save()
        rc = IgnorePatterns(
            domain=DOMAIN,
            case_type='case_type',
            case_property='phone_number',
            regex='+',
        )                       # remove '+' from the phone_number case property
        rc.save()
        self.config.ignore_patterns.add(rc)
        self.config.save()

        criteria = OrderedDict([
            ('phone_number', '+91999'),
            ('special_id', 'abc-123-546'),
            ('name', "this word should be gone"),
            ('other_name', "this word should not be gone"),
        ])

        expected = {"query": {
            "filtered": {
                "filter": {
                    "and": [
                        {
                            "term": {
                                "domain.exact": "swashbucklers"
                            }
                        },
                        {
                            "term": {
                                "type.exact": "case_type"
                            }
                        },
                        {
                            "term": {
                                "closed": False
                            }
                        },
                        {
                            "match_all": {}
                        }
                    ]
                },
                "query": {
                    "bool": {
                        "must": [
                            {
                                "nested": {
                                    "path": "case_properties",
                                    "query": {
                                        "filtered": {
                                            "filter": {
                                                "and": (
                                                    {
                                                        "term": {
                                                            "case_properties.key.exact": "phone_number"
                                                        }
                                                    },
                                                    {
                                                        "term": {
                                                            "case_properties.value.exact": "91999"
                                                        }
                                                    }
                                                ),
                                            },
                                            "query": {
                                                "match_all": {
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
                                                "and": (
                                                    {
                                                        "term": {
                                                            "case_properties.key.exact": "special_id"
                                                        }
                                                    },
                                                    {
                                                        "term": {
                                                            "case_properties.value.exact": "abc123546"
                                                        }
                                                    }
                                                )

                                            },
                                            "query": {
                                                "match_all": {
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
                                                "and": (
                                                    {
                                                        "term": {
                                                            "case_properties.key.exact": "name"
                                                        }
                                                    },
                                                    {
                                                        "term": {
                                                            "case_properties.value.exact": "this should be"
                                                        }
                                                    }
                                                )

                                            },
                                            "query": {
                                                "match_all": {
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
                                                "and": (
                                                    {
                                                        "term": {
                                                            "case_properties.key.exact": "other_name"
                                                        }
                                                    },
                                                    {
                                                        "term": {
                                                            "case_properties.value.exact": (
                                                                "this word should not be gone"
                                                            )
                                                        }
                                                    }
                                                )
                                            },
                                            "query": {
                                                "match_all": {
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        },
            "size": CASE_SEARCH_MAX_RESULTS,
        }
        self.checkQuery(
            CaseSearchCriteria(DOMAIN, 'case_type', criteria).search_es,
            expected,
        )


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
        CaseSearchReindexerFactory(domain=DOMAIN).build().reindex()
        es = get_es_new()
        es.indices.refresh(CASE_SEARCH_INDEX)

    def tearDown(self):
        ensure_index_deleted(CASE_SEARCH_INDEX)
        self.user.delete()
        self.domain.delete()
        for query_addition in CaseSearchQueryAddition.objects.all():
            query_addition.delete()
        cache = get_redis_default_cache()
        cache.clear()

    @run_with_all_backends
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

    @run_with_all_backends
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
        self.assertEqual(response.content.decode('utf-8'), 'You have already claimed that case')

    @run_with_all_backends
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
        self.assertEqual(response.content.decode('utf-8'), 'You have already claimed that case')

    @flaky
    @run_with_all_backends
    def test_claim_restore_as(self):
        """Server should assign cases to the correct user
        """
        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        other_user_username = 'other_user@{}.commcarehq.org'.format(DOMAIN)
        other_user = CommCareUser.create(DOMAIN, other_user_username, PASSWORD)

        url = reverse('claim_case', kwargs={'domain': DOMAIN})

        client.post(url, {
            'case_id': self.case_id,
            'commcare_login_as': other_user_username
        })

        claim_ids = CaseAccessors(DOMAIN).get_case_ids_in_domain(CLAIM_CASE_TYPE)
        self.assertEqual(len(claim_ids), 1)

        claim_case = CaseAccessors(DOMAIN).get_case(claim_ids[0])
        self.assertEqual(claim_case.owner_id, other_user._id)

    def test_claim_restore_as_proper_cache(self):
        """Server should assign cases to the correct user
        """
        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        other_user_username = 'other_user@{}.commcarehq.org'.format(DOMAIN)
        other_user = CommCareUser.create(DOMAIN, other_user_username, PASSWORD)

        another_user_username = 'another_user@{}.commcarehq.org'.format(DOMAIN)
        another_user = CommCareUser.create(DOMAIN, another_user_username, PASSWORD)

        url = reverse('claim_case', kwargs={'domain': DOMAIN})

        client.post(url, {
            'case_id': self.case_id,
            'commcare_login_as': other_user_username
        })

        claim_ids = CaseAccessors(DOMAIN).get_case_ids_in_domain(CLAIM_CASE_TYPE)
        self.assertEqual(len(claim_ids), 1)

        claim_case = CaseAccessors(DOMAIN).get_case(claim_ids[0])
        self.assertEqual(claim_case.owner_id, other_user._id)

        client.post(url, {
            'case_id': self.case_id,
            'commcare_login_as': another_user_username
        })

        # We've now created two claims
        claim_ids = CaseAccessors(DOMAIN).get_case_ids_in_domain(CLAIM_CASE_TYPE)
        self.assertEqual(len(claim_ids), 2)

        # The most recent one should be the extension owned by the other user
        claim_cases = CaseAccessors(DOMAIN).get_cases(claim_ids)
        self.assertIn(another_user._id, [case.owner_id for case in claim_cases])

    @run_with_all_backends
    def test_search_endpoint(self):
        self.maxDiff = None
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
            '<commcare_search_score>xxx</commcare_search_score>'
            '<location_id>None</location_id>'
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
        score_regex = re.compile(r'(<commcare_search_score>)(\d+.\d+)(<\/commcare_search_score>)')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            score_regex.sub(r'\1xxx\3',
                            re.sub(DATE_PATTERN, FIXED_DATESTAMP,
                                   re.sub(PATTERN, TIMESTAMP, response.content.decode('utf-8')))),
            known_result)

    @patch('corehq.apps.es.es_query.run_query')
    def test_search_query_addition(self, run_query_mock):
        self.maxDiff = None
        new_must_clause = {
            "bool": {
                "should": [
                    {
                        "nested": {
                            "path": "case_properties",
                            "query": {
                                "filtered": {
                                    "filter": {
                                        "and": [
                                            {
                                                "term": {
                                                    "case_properties.key.exact": "is_inactive"
                                                }
                                            },
                                            {
                                                "term": {
                                                    "case_properties.value.exact": "yes"
                                                }
                                            }
                                        ]
                                    },
                                    "query": {
                                        "match_all": {
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
                                        "and": [
                                            {
                                                "term": {
                                                    "case_properties.key.exact": "awaiting_claim"
                                                }
                                            },
                                            {
                                                "term": {
                                                    "case_properties.value.exact": "yes"
                                                }
                                            }
                                        ]
                                    },
                                    "query": {
                                        "match_all": {
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
                                                'filter': {
                                                    "and": (
                                                        {
                                                            'term': {'case_properties.key.exact': 'name'}
                                                        },
                                                        {
                                                            'term': {'case_properties.value.exact': some_case_name}
                                                        }
                                                    )
                                                },
                                                'query': {
                                                    'match_all': {
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
            'size': CASE_SEARCH_MAX_RESULTS
        }
        run_query_mock.assert_called_with(
            "case_search",
            expected_query,
            debug_host=None,
            es_instance_alias=ES_DEFAULT_INSTANCE,
        )
