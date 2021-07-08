import re
from collections import OrderedDict
from uuid import uuid4

from django.test import Client, TestCase
from django.urls import reverse

from flaky import flaky

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.util import post_case_blocks
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.case_search.const import CASE_SEARCH_MAX_RESULTS
from corehq.apps.case_search.models import (
    CLAIM_CASE_TYPE,
    CASE_SEARCH_XPATH_QUERY_KEY,
    CaseSearchConfig,
    IgnorePatterns,
)
from corehq.apps.case_search.utils import CaseSearchCriteria
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.pillows.case_search import CaseSearchReindexerFactory, domains_needing_search_index
from corehq.pillows.mappings.case_search_mapping import (
    CASE_SEARCH_INDEX,
    CASE_SEARCH_INDEX_INFO,
)
from corehq.util.elastic import ensure_index_deleted

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


@es_test
class CaseSearchTests(ElasticTestMixin, TestCase):
    def setUp(self):
        super(CaseSearchTests, self).setUp()
        self.config, created = CaseSearchConfig.objects.get_or_create(pk=DOMAIN, enabled=True)

    def test_add_blacklisted_ids(self):
        criteria = {
            "commcare_blacklisted_owner_ids": "id1 id2 id3,id4"
        }
        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {'term': {'domain.exact': 'swashbucklers'}},
                        {"terms": {"type.exact": ["case_type"]}},
                        {"term": {"closed": False}},
                        {
                            "bool": {
                                "must_not": {
                                    "term": {
                                        "owner_id": "id1"
                                    }
                                }
                            }
                        },
                        {
                            "bool": {
                                "must_not": {
                                    "term": {
                                        "owner_id": "id2"
                                    }
                                }
                            }
                        },
                        {
                            "bool": {
                                "must_not": {
                                    "term": {
                                        "owner_id": "id3,id4"
                                    }
                                }
                            }
                        },
                        {"match_all": {}}
                    ],
                    "must": {
                        "match_all": {}
                    }
                }
            },
            "sort": [
                "_score",
                "_doc"
            ],
            "size": CASE_SEARCH_MAX_RESULTS
        }

        self.checkQuery(
            CaseSearchCriteria(DOMAIN, ['case_type'], criteria).search_es,
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

        expected = {
            "query": {
                "bool": {
                    "filter": [
                        {'term': {'domain.exact': 'swashbucklers'}},
                        {"terms": {"type.exact": ["case_type"]}},
                        {"term": {"closed": False}},
                        {"match_all": {}}
                    ],
                    "must": {
                        "bool": {
                            "must": [
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "bool": {
                                                "filter": [
                                                    {
                                                        "bool": {
                                                            "filter": [
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
                                                            ]
                                                        }
                                                    }
                                                ],
                                                "must": {
                                                    "match_all": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "bool": {
                                                "filter": [
                                                    {
                                                        "bool": {
                                                            "filter": [
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
                                                            ]
                                                        }
                                                    }
                                                ],
                                                "must": {
                                                    "match_all": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "bool": {
                                                "filter": [
                                                    {
                                                        "bool": {
                                                            "filter": [
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
                                                            ]
                                                        }
                                                    }
                                                ],
                                                "must": {
                                                    "match_all": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "nested": {
                                        "path": "case_properties",
                                        "query": {
                                            "bool": {
                                                "filter": [
                                                    {
                                                        "bool": {
                                                            "filter": [
                                                                {
                                                                    "term": {
                                                                        "case_properties.key.exact": "other_name"
                                                                    }
                                                                },
                                                                {
                                                                    "term": {
                                                                        "case_properties.value.exact": "this word should not be gone"
                                                                    }
                                                                }
                                                            ]
                                                        }
                                                    }
                                                ],
                                                "must": {
                                                    "match_all": {}
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
            "sort": [
                "_score",
                "_doc"
            ],
            "size": CASE_SEARCH_MAX_RESULTS
        }
        self.checkQuery(
            CaseSearchCriteria(DOMAIN, ['case_type'], criteria).search_es,
            expected,
            validate_query=False
        )


@es_test
class CaseClaimEndpointTests(TestCase):
    def setUp(self):
        self.domain = create_domain(DOMAIN)
        self.user = CommCareUser.create(DOMAIN, USERNAME, PASSWORD, None, None)
        initialize_index_and_mapping(get_es_new(), CASE_SEARCH_INDEX_INFO)
        CaseSearchConfig.objects.get_or_create(pk=DOMAIN, enabled=True)
        delete_all_cases()
        self.case_id = uuid4().hex
        _, [self.case] = post_case_blocks([CaseBlock.deprecated_init(
            create=True,
            case_id=self.case_id,
            case_type=CASE_TYPE,
            case_name=CASE_NAME,
            external_id=CASE_NAME,
            user_id=OWNER_ID,
            owner_id=OWNER_ID,
            update={'opened_by': OWNER_ID},
        ).as_xml()], {'domain': DOMAIN})
        domains_needing_search_index.clear()
        CaseSearchReindexerFactory(domain=DOMAIN).build().reindex()
        es = get_es_new()
        es.indices.refresh(CASE_SEARCH_INDEX)

    def tearDown(self):
        ensure_index_deleted(CASE_SEARCH_INDEX)
        self.user.delete(self.domain.name, deleted_by=None)
        self.domain.delete()
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
        other_user = CommCareUser.create(DOMAIN, other_user_username, PASSWORD, None, None)

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
        other_user = CommCareUser.create(DOMAIN, other_user_username, PASSWORD, None, None)

        another_user_username = 'another_user@{}.commcarehq.org'.format(DOMAIN)
        another_user = CommCareUser.create(DOMAIN, another_user_username, PASSWORD, None, None)

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
        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        url = reverse('remote_search', kwargs={'domain': DOMAIN})

        matching_criteria = [
            {'name': 'Jamie Hand'},
            {'name': 'Jamie Hand', CASE_SEARCH_XPATH_QUERY_KEY: 'date_opened > "2015-03-25"'},
            {CASE_SEARCH_XPATH_QUERY_KEY: 'name = "not Jamie" or name = "Jamie Hand"'},
        ]
        for params in matching_criteria:
            params.update({'case_type': CASE_TYPE})
            response = client.get(url, params)
            self._assert_known_search_result(response, params)

        non_matching_criteria = [
            {'name': 'Jamie Face'},
            {'name': 'Jamie Hand', CASE_SEARCH_XPATH_QUERY_KEY: 'date_opened < "2015-03-25"'},
            {CASE_SEARCH_XPATH_QUERY_KEY: 'name = "not Jamie" and name = "Jamie Hand"'},
        ]
        for params in non_matching_criteria:
            params.update({'case_type': CASE_TYPE})
            response = client.get(url, params)
            self._assert_empty_search_result(response, params)

    def _assert_known_search_result(self, response, message=None):
        self.assertEqual(response.status_code, 200, message)
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
        score_regex = re.compile(r'(<commcare_search_score>)(\d+.\d+)(<\/commcare_search_score>)')
        self.assertEqual(
            score_regex.sub(r'\1xxx\3',
                            re.sub(DATE_PATTERN, FIXED_DATESTAMP,
                                   re.sub(PATTERN, TIMESTAMP, response.content.decode('utf-8')))),
            known_result,
            message)

    def _assert_empty_search_result(self, response, message=None):
        self.assertEqual(response.status_code, 200, message)
        self.assertEqual('<results id="case" />', response.content.decode('utf-8'), message)
