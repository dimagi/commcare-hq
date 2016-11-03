import json
import os
import uuid
from StringIO import StringIO
from collections import Counter

from django.test import TestCase
from fakecouch import FakeCouchDb

from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.models import Domain
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.couch import CouchDataLoader
from corehq.apps.dump_reload.couch.dump import get_doc_ids_to_dump
from corehq.apps.dump_reload.util import get_model_label
from corehq.util.couch import get_document_class_by_doc_type
from corehq.util.test_utils import mock_out_couch
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.couch.database import iter_docs


class CouchDumpLoadTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(CouchDumpLoadTest, cls).setUpClass()
        cls.domain_name = uuid.uuid4().hex
        cls.domain = Domain(name=cls.domain_name)
        cls.domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(CouchDumpLoadTest, cls).tearDownClass()

    def tearDown(self):
        self._delete_couch_data()

    def _delete_couch_data(self):
        for doc_class, doc_ids in get_doc_ids_to_dump(self.domain_name):
            db = doc_class.get_db()
            for docs in chunked(iter_docs(db, doc_ids), 100):
                db.bulk_delete(docs)

            self.assertEqual(0, len(get_docs(db, doc_ids)))

    def _dump_and_load(self, expected_object_counts):
        output_stream = StringIO()
        CouchDataDumper(self.domain_name, []).dump(output_stream)

        self._delete_couch_data()

        # make sure that there's no data left in the DB
        objects_remaining = _get_doc_counts_from_db(self.domain_name)
        self.assertEqual({}, objects_remaining, 'Not all data deleted: {}'.format(objects_remaining))

        dump_output = output_stream.getvalue()
        dump_lines = [line.strip() for line in dump_output.split('\n') if line.strip()]

        with mock_out_couch() as fake_db:
            total_object_count, loaded_object_count = CouchDataLoader().load_objects(dump_lines)

        actual_model_counts = Counter([
            get_document_class_by_doc_type(json.loads(line)['doc_type'])
            for line in dump_lines
        ])
        expected_total_objects = sum(expected_object_counts.values())
        self.assertDictEqual(expected_object_counts, actual_model_counts)
        self.assertEqual(expected_total_objects, sum(loaded_object_count.values()))
        self.assertEqual(expected_total_objects, total_object_count)

        counts_in_fake_db = _get_doc_counts_from_fake_db(fake_db)
        self.assertDictEqual(expected_object_counts, counts_in_fake_db)

        return fake_db

    def test_location(self):
        from corehq.apps.locations.models import Location
        expected_model_counts = {
            Location: 1
        }
        make_loc('ct', 'Cape Town', domain=self.domain_name, type='city')

        self._dump_and_load(expected_model_counts)

    def test_applications(self):
        from corehq.apps.app_manager.models import Application

        path = os.path.join(
            'corehq', 'apps', 'app_manager', 'tests', 'data', 'suite', 'app.json'
        )
        with open(path) as f:
            source = json.load(f)

        app = Application.wrap(source)
        app.domain = self.domain_name
        app.save()

        fakedb = self._dump_and_load({
            Application: 1
        })

        copied_app_source = fakedb.get(app._id)
        self.assertDictEqual(app.to_json(), copied_app_source)


def _get_doc_counts_from_db(domain):
    return {
        get_model_label(doc_class): len(doc_ids)
        for doc_class, doc_ids in get_doc_ids_to_dump(domain) if doc_ids
    }


def _get_doc_counts_from_fake_db(fake_db):
    return dict(Counter(
        get_document_class_by_doc_type(doc['doc_type'])
        for doc in fake_db.mock_docs.values()
    ))
