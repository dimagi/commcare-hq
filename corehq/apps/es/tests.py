"""
This file is a decent reference for seeing how the query builder maps to
the eventual elasticsearch query.
"""
import json
from unittest import TestCase

from .es_query import HQESQuery
from . import forms, users


class TestHQESQuery(TestCase):
    maxDiff = 1000

    def checkQuery(self, query, json_output):
        msg = "Expected Query:\n{}\nGenerated Query:\n{}".format(
                query.dumps(pretty=True),
                json.dumps(json_output, indent=4),
            )
        # NOTE: This method thinks [a, b, c] != [b, c, a], which it is
        # in elasticsearch; order doesn't matter
        self.assertEqual(query.raw_query, json_output, msg=msg)

    def test_basic_query(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"match_all": {}}
                        ]
                    },
                    "query": {"match_all": {}}
                }
            }
        }
        self.checkQuery(HQESQuery('forms'), json_output)

    def test_form_query(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"doc_type": "xforminstance"}},
                            {"not": {"missing":
                                {"field": "xmlns"}}},
                            {"not": {"missing":
                                {"field": "form.meta.userID"}}},
                        ]
                    },
                    "query": {"match_all": {}}
                }
            }
        }
        query = forms.FormsES()
        self.checkQuery(query, json_output)

    def test_user_query(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"is_active": True}},
                            {"term": {"doc_type": "CommCareUser"}},
                            {"term": {"base_doc": "couchuser"}},
                        ]
                    },
                    "query": {"match_all": {}}
                }
            }
        }
        query = users.UserES()
        self.checkQuery(query, json_output)

    def test_filtered_forms(self):
        json_output = {
            "query": {
                "filtered": {
                    "filter": {
                        "and": [
                            {"term": {"doc_type": "xforminstance"}},
                            {"not": {"missing":
                                {"field": "xmlns"}}},
                            {"not": {"missing":
                                {"field": "form.meta.userID"}}},
                        ]
                    },
                    "query": {"match_all": {}}
                }
            }
        }
        query = forms.FormsES()
        # TODO add filters
        # self.checkQuery(query, json_output)


class TestESQuerySet(TestCase):
    example_response = {
        u'_shards': {u'failed': 0, u'successful': 5, u'total': 5},
        u'hits': {u'hits': [ {
            u'_id': u'8063dff5-460b-46f2-b4d0-5871abfd97d4',
            u'_index': u'xforms_1cce1f049a1b4d864c9c25dc42648a45',
            u'_score': 1.0,
            u'_type': u'xform',
            u'fields': {
                u'app_id': u'fe8481a39c3738749e6a4766fca99efd',
                u'doc_type': u'xforminstance',
                u'domain': u'mikesproject',
                u'xmlns': u'http://openrosa.org/formdesigner/3a7cc07c-551c-4651-ab1a-d60be3017485'
                }
            },
            {
                u'_id': u'dc1376cd-0869-4c13-a267-365dfc2fa754',
                u'_index': u'xforms_1cce1f049a1b4d864c9c25dc42648a45',
                u'_score': 1.0,
                u'_type': u'xform',
                u'fields': {
                    u'app_id': u'3d622620ca00d7709625220751a7b1f9',
                    u'doc_type': u'xforminstance',
                    u'domain': u'mikesproject',
                    u'xmlns': u'http://openrosa.org/formdesigner/54db1962-b938-4e2b-b00e-08414163ead4'
                    }
                }
            ],
            u'max_score': 1.0,
            u'total': 5247
            },
        u'timed_out': False,
        u'took': 4
        }
    example_error = {u'error': u'IndexMissingException[[xforms_123jlajlaf] missing]',
             u'status': 404}
