from django.conf import settings
from django.test import SimpleTestCase, override_settings

from corehq.apps.es import canonical_name_adapter_map
from corehq.apps.es.migration_operations import CreateIndex
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es import const as es_const
from corehq.pillows.utils import get_all_expected_es_indices


@es_test
@override_settings(IS_SAAS_ENVIRONMENT=True)
class ProdIndexManagementTest(SimpleTestCase):

    maxDiff = None  # show the entire diff for test failures

    @classmethod
    def setUpClass(cls):
        super(ProdIndexManagementTest, cls).setUpClass()
        cls._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS
        canonical_name_adapter_map.reset_cache()
        cls.addClassCleanup(canonical_name_adapter_map.reset_cache)

    @classmethod
    def tearDownClass(cls):
        settings.PILLOWTOPS = cls._PILLOWTOPS
        super(ProdIndexManagementTest, cls).tearDownClass()

    def test_prod_config(self):
        # TODO: implement index verification in a way that is reindex-friendly
        found_prod_indices = []
        for adapter in get_all_expected_es_indices():
            meta = CreateIndex.render_index_metadata(
                adapter.type, adapter.mapping,
                adapter.analysis, adapter.settings_key, 'index meta'
            )
            # for now don"t test this property, just ensure it exist
            self.assertTrue(meta['mappings'])
            del meta['mappings']

            index_details = {
                'index': adapter.index_name,
                'type': adapter.type,
                'hq_index_name': adapter.settings_key,
                'meta': meta
            }
            found_prod_indices.append(index_details)

            # TODO: test mappings.  Seems related, but different from
            # `corehq/pillows/mappings/tests`. The tests here in this module
            # should probably move over there some day.

        def index_name(info):
            return info['index']

        found_prod_indices = sorted(found_prod_indices, key=index_name)
        expected_prod_indices = sorted(EXPECTED_PROD_INDICES, key=index_name)
        # compare aliases to make it easier to spot the difference
        # when an index is added or removed
        self.assertEqual(
            [index_name(info) for info in expected_prod_indices],
            [index_name(info) for info in found_prod_indices],
        )
        # do full comparison once we know the index aliases are the same
        self.assertEqual(expected_prod_indices, found_prod_indices)


EXPECTED_PROD_INDICES = [
    {
        "index": f"test_{es_const.HQ_CASE_SEARCH_INDEX_NAME}",
        "type": "case",
        "hq_index_name": "case_search",
        "meta": {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "custom",
                            "tokenizer": "whitespace",
                            "filter": [
                                "lowercase"
                            ]
                        },
                        "phonetic": {
                            "filter": [
                                "standard",
                                "lowercase",
                                "soundex"
                            ],
                            "tokenizer": "standard"
                        }
                    },
                    "filter": {
                        "soundex": {
                            "replace": "true",
                            "type": "phonetic",
                            "encoder": "soundex"
                        }
                    }
                },
                "number_of_replicas": 0,
                "number_of_shards": 1,
            }
        }
    },
    {
        "index": f"test_{es_const.HQ_CASE_SEARCH_BHA_INDEX_NAME}",
        "type": "case",
        "hq_index_name": "case_search_bha",
        "meta": {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "custom",
                            "tokenizer": "whitespace",
                            "filter": [
                                "lowercase"
                            ]
                        },
                        "phonetic": {
                            "filter": [
                                "standard",
                                "lowercase",
                                "soundex"
                            ],
                            "tokenizer": "standard"
                        }
                    },
                    "filter": {
                        "soundex": {
                            "replace": "true",
                            "type": "phonetic",
                            "encoder": "soundex"
                        }
                    }
                },
                "number_of_replicas": 0,
                "number_of_shards": 1,
            }
        }
    },
    {
        "hq_index_name": "hqapps",
        "index": f"test_{es_const.HQ_APPS_INDEX_NAME}",
        "type": "app",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "number_of_shards": 1,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "custom",
                            "tokenizer": "whitespace",
                            "filter": ["lowercase"]
                        },
                    }
                }
            }
        }
    },
    {
        "hq_index_name": "hqcases",
        "index": f"test_{es_const.HQ_CASES_INDEX_NAME}",
        "type": "case",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "number_of_shards": 1,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        }
                    }
                }
            }
        }
    },
    {
        "hq_index_name": "hqdomains",
        "index": f"test_{es_const.HQ_DOMAINS_INDEX_NAME}",
        "type": "hqdomain",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "number_of_shards": 1,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "custom",
                            "tokenizer": "whitespace",
                            "filter": ["lowercase"]
                        },
                        "comma": {
                            "type": "pattern",
                            "pattern": r"\s*,\s*"
                        },
                    }
                }
            }
        }
    },
    {
        "hq_index_name": "hqgroups",
        "index": f"test_{es_const.HQ_GROUPS_INDEX_NAME}",
        "type": "group",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "number_of_shards": 1,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        }
                    }
                }
            }
        }
    },
    {
        "hq_index_name": "hqusers",
        "index": f"test_{es_const.HQ_USERS_INDEX_NAME}",
        "type": "user",
        "meta": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "custom",
                            "tokenizer": "whitespace",
                            "filter": ["lowercase"]
                        },
                    }
                }
            }
        }
    },
    {
        "hq_index_name": "smslogs",
        "index": f"test_{es_const.HQ_SMS_INDEX_NAME}",
        "type": "sms",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "number_of_shards": 1,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        }
                    }
                }
            }
        }
    },
    {
        "hq_index_name": "xforms",
        "index": f"test_{es_const.HQ_FORMS_INDEX_NAME}",
        "type": "xform",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "number_of_shards": 1,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        }
                    }
                }
            }
        }
    }
]
