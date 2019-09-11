import unittest
import uuid
from unittest import TestCase

from datetime import datetime

from corehq.apps.api.es import XFormES
from corehq.apps.api.tests.utils import ESTest
from corehq.blobs.mixin import BlobMetaRef
from corehq.elastic import send_to_elasticsearch
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.util.test_utils import make_es_ready_form


class TestXFormES(ESTest):
    '''
    Tests the ElasticSearch XForm module
    '''

    @classmethod
    def setUpClass(cls):
        super(TestXFormES, cls).setUpClass()
        cls.xform_es = XFormES(cls.domain.name)
        form_data = {
            'user_id': 'dean_martin',
            'app_id': '4pp123',
            'form_name': 'Lovely form',
            'xmlns': 'http://this.that.org/abc'
        }
        cls._create_es_form(attachment_dict={"addition": {"Louis":"Armstrong"}}, **form_data)
        pass

    @classmethod
    def tearDownClass(cls):
        super(TestXFormES, cls).tearDownClass()
        pass

    @classmethod
    def _create_es_form(cls, domain=None, attachment_dict=None, **metadata_kwargs):
        attachment_dict = attachment_dict or {}
        metadata = TestFormMetadata(
            domain=domain or uuid.uuid4().hex,
            time_end=datetime.utcnow(),
            received_on=datetime.utcnow(),
        )

        for attr, value in metadata_kwargs.items():
            setattr(metadata, attr, value)

        form_pair = make_es_ready_form(metadata)
        if attachment_dict:
            form_pair.wrapped_form.external_blobs = {
                name: BlobMetaRef(**meta)
                for name, meta in attachment_dict.items()
            }
            form_pair.json_form['external_blobs'] = attachment_dict

        es_form = transform_xform_for_elasticsearch(form_pair.json_form)
        send_to_elasticsearch('forms', es_form)
        cls.es.indices.refresh(XFORM_INDEX_INFO.index)
        return form_pair

    @run_with_all_backends
    def test_base_query(self):
        actual = self.xform_es.base_query(terms={'a': 'b'},fields={'champ':'de mars'})
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
            'fields': {'champ': 'de mars'}

        }

        self.assertDictEqual(actual, expected)

    

