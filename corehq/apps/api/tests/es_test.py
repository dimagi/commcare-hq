import unittest
import uuid
from unittest import TestCase

from datetime import datetime

from elasticsearch import Elasticsearch

from corehq.apps.api.es import XFormES, UserES, ESUserError, ReportXFormES, ESView
from corehq.apps.api.tests.utils import ESTest
from corehq.apps.users.models import CommCareUser
from corehq.blobs.mixin import BlobMetaRef
from corehq.elastic import send_to_elasticsearch
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import make_es_ready_form


class FormTestES(ESTest):

    @classmethod
    def setUpClass(cls):
        super(FormTestES, cls).setUpClass()
        form_data = {
            'user_id': 'dean_martin',
            'app_id': '4pp123',
            'form_name': 'Lovely form',
            'xmlns': 'http://this.that.org/abc'
        }
        cls.form_pair = cls._create_es_form(
            domain=cls.domain.name,
            **form_data)
        pass

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        super(FormTestES, cls).tearDownClass()
        pass

    @classmethod
    def _create_es_form(cls, domain=None, **metadata_kwargs):
        metadata = TestFormMetadata(
            domain=domain or uuid.uuid4().hex,
            time_end=datetime.utcnow(),
            received_on=datetime.utcnow(),
        )

        for attr, value in metadata_kwargs.items():
            setattr(metadata, attr, value)

        form_pair = make_es_ready_form(metadata)

        cls.es_form = transform_xform_for_elasticsearch(form_pair.json_form)
        send_to_elasticsearch('forms', cls.es_form)
        cls.es.indices.refresh(XFORM_INDEX_INFO.index)
        return form_pair


class TestESView(ESTest):

    @classmethod
    def setUpClass(cls):
        super(TestESView, cls).setUpClass()
        cls.es_view = ESView(cls.domain.name)
        pass

    @classmethod
    def tearDownClass(cls):
        super(TestESView, cls).tearDownClass()
        pass

    def test_not_implemented_head(self):
        with self.assertRaises(NotImplementedError):
            head = self.es_view.head()



class TestXFormES(FormTestES):

    @classmethod
    def setUpClass(cls):
        super(TestXFormES, cls).setUpClass()
        cls.xform_es = XFormES(cls.domain.name)

    @classmethod
    def tearDownClass(cls):
        super(TestXFormES, cls).tearDownClass()
        pass

    @run_with_all_backends
    def test_base_query(self):
        actual = self.xform_es.base_query(terms={'a': 'b'},fields=['doc_type'])
        expected = {
            'filter': {
                'and':  [
                    {'term': {'domain.exact': 'elastico'}},
                    {'term': {'a': 'b'}},
                    {'term': {'doc_type': 'xforminstance'}}
                ]
            },
            'from': 0,
            'size': 10,
            'fields': ['doc_type']
        }

        self.assertDictEqual(actual, expected)

    @run_with_all_backends
    def test_run_query(self):
        query = {
            "query": {
                "filtered": {
                    "query": {"match_all": {}},
                    "filter": {"term": {"doc_type": "xforminstance"}}
                }
            }
        }

        result = self.xform_es.run_query(query)
        self.assertEqual(result['hits']['total'], 1)


class TestUserES(ESTest):

    @classmethod
    def setUpClass(cls):
        super(TestUserES, cls).setUpClass()
        cls.user_es = UserES(cls.domain.name)
        cls._send_user_to_es()
        pass

    @classmethod
    def tearDownClass(cls):
        delete_es_index(USER_INDEX_INFO.index)
        super(TestUserES, cls).tearDownClass()
        pass

    @classmethod
    def _send_user_to_es(cls, _id=None, is_active=True):
        user = CommCareUser(
            domain=cls.domain.name,
            username="johann_strauss",
            _id=_id or uuid.uuid4().hex,
            is_active=is_active,
            first_name="Johann",
            last_name="Strauss",
        )

        send_to_elasticsearch('users', user.to_json())
        cls.es.indices.refresh(USER_INDEX_INFO.index)
        cls.user = user

    @run_with_all_backends
    def test_query_validation(self):
        query = {
            "fields": ['password']
        }

        with self.assertRaises(ESUserError):
            self.user_es.run_query(query)

    @run_with_all_backends
    def test_run_query(self):
        query = {
            "query": {
                "filtered": {
                    "query": {"match_all": {}},
                    'filter': {
                        'and': [
                            {'term': {'username': "johann_strauss"}}
                        ]
                    }
                }

            },
            "fields": ["username", "domain"]
        }

        result = self.user_es.run_query(query, security_check=False)
        self.assertEqual(result['hits']['total'], 1)
        self.assertEqual(result['hits']['hits'][0]['fields']['username'][0],
                         self.user.username)


class TestReportFormES(FormTestES):

    @classmethod
    def setUpClass(cls):
        super(TestReportFormES, cls).setUpClass()
        cls.report_xform_es = ReportXFormES(cls.domain.name)

        send_to_elasticsearch('report_xforms', cls.es_form)
        cls.es.indices.refresh(REPORT_XFORM_INDEX_INFO.index)

        pass

    @classmethod
    def tearDownClass(cls):
        super(TestReportFormES, cls).tearDownClass()
        delete_es_index(REPORT_XFORM_INDEX_INFO.index)
        pass

    @run_with_all_backends
    def test_base_query(self):
        actual = self.report_xform_es.base_query(terms={'a': 'b'},fields=['doc_type'])
        expected = {
            'filter': {
                'and':  [
                    {'term': {'domain.exact': 'elastico'}},
                    {'term': {'a': 'b'}},
                    {'term': {'doc_type': 'xforminstance'}}
                ]
            },
            'from': 0,
            'size': 10,
            'fields': ['doc_type']
        }

        self.assertDictEqual(actual, expected)

    @run_with_all_backends
    def test_run_query(self):
        query = {
            "query": {
                "filtered": {
                    "query": {"match_all": {}},
                    "filter": {"term": {"doc_type": "xforminstance"}}
                }
            }
        }

        result = self.report_xform_es.run_query(query)
        self.assertEqual(result['hits']['total'], 1)
