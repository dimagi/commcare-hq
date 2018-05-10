from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from django.test import SimpleTestCase
from django.test.utils import override_settings
from corehq.pillows.utils import get_all_expected_es_indices


class ProdIndexManagementTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super(ProdIndexManagementTest, cls).setUpClass()
        cls._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS

    @classmethod
    def tearDownClass(cls):
        settings.PILLOWTOPS = cls._PILLOWTOPS
        super(ProdIndexManagementTest, cls).tearDownClass()

    @override_settings(SERVER_ENVIRONMENT='production')
    def test_prod_config(self):
        found_prod_indices = [info.to_json() for info in get_all_expected_es_indices()]
        for info in found_prod_indices:
            # for now don't test this property, just ensure it exist
            self.assertTrue(info['mapping'])
            del info['mapping']
        found_prod_indices = sorted(found_prod_indices, key=lambda info: info['index'])
        self.assertEqual(EXPECTED_PROD_INDICES, found_prod_indices)


EXPECTED_PROD_INDICES = [
    {
        "alias": "case_search",
        "index": "test_case_search_2018-04-27",
        "type": "case",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        },
                        "sortable_exact": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "keyword"
                        }
                    }
                }
            }
        }
    },
    {
        "alias": "hqapps",
        "index": "test_hqapps_2017-05-22_1426",
        "type": "app",
        "meta": {
            "settings": {
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
        "alias": "hqcases",
        "index": "test_hqcases_2016-03-04",
        "type": "case",
        "meta": {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        },
                        "sortable_exact": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "keyword"
                        }
                    }
                }
            }
        }
    },
    {
        "alias": "hqdomains",
        "index": "test_hqdomains_2016-08-08",
        "type": "hqdomain",
        "meta": {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "custom",
                            "tokenizer": "whitespace",
                            "filter": ["lowercase"]
                        },
                        "comma": {
                            "type": "pattern",
                            "pattern": "\s*,\s*"
                        },
                    }
                }
            }
        }
    },
    {
        "alias": "hqgroups",
        "index": "test_hqgroups_2017-05-29",
        "type": "group",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        },
                        "sortable_exact": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "keyword"
                        }
                    }
                }
            }
        }
    },
    {
        "alias": "hqusers",
        "index": "test_hqusers_2017-09-07",
        "type": "user",
        "meta": {
            "settings": {
                "number_of_shards": 2,
                "number_of_replicas": 1,
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
        "alias": "ledgers",
        "index": "test_ledgers_2016-03-15",
        "type": "ledger",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        },
                        "sortable_exact": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "keyword"
                        }
                    }
                }
            }
        }
    },
    {
        "alias": "report_cases",
        "index": "test_report_cases_czei39du507m9mmpqk3y01x72a3ux4p0",
        "type": "report_case",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        },
                        "sortable_exact": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "keyword"
                        }
                    }
                }
            }
        }
    },
    {
        "alias": "report_xforms",
        "index": "test_report_xforms_20160824_1708",
        "type": "report_xform",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        },
                        "sortable_exact": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "keyword"
                        }
                    }
                }
            }
        }
    },
    {
        "alias": "smslogs",
        "index": "test_smslogs_2017-02-09",
        "type": "sms",
        "meta": {
            "settings": {
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        },
                        "sortable_exact": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "keyword"
                        }
                    }
                }
            }
        }
    },
    {
        "alias": "xforms",
        "index": "test_xforms_2016-07-07",
        "type": "xform",
        "meta": {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "whitespace"
                        },
                        "sortable_exact": {
                            "filter": [
                                "lowercase"
                            ],
                            "type": "custom",
                            "tokenizer": "keyword"
                        }
                    }
                }
            }
        }
    }
]
