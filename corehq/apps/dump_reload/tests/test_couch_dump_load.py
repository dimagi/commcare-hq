import json
import os
import random
import uuid
from collections import Counter
from io import StringIO

from django.test import SimpleTestCase, TestCase

from couchdbkit.exceptions import ResourceNotFound
from mock import Mock

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.couch.database import iter_docs

from corehq.apps.domain.models import Domain
from corehq.apps.dump_reload.couch import CouchDataDumper, CouchDataLoader
from corehq.apps.dump_reload.couch.dump import (
    DOC_PROVIDERS,
    ToggleDumper,
    get_doc_ids_to_dump,
)
from corehq.apps.dump_reload.couch.id_providers import DocTypeIDProvider
from corehq.apps.dump_reload.couch.load import ToggleLoader
from corehq.apps.dump_reload.util import get_model_label
from corehq.apps.userreports.const import VALID_REFERENCED_DOC_TYPES
from corehq.toggles import NAMESPACE_DOMAIN, all_toggles
from corehq.util.couch import get_document_class_by_doc_type
from corehq.util.test_utils import mock_out_couch


class CouchDumpLoadTest(TestCase):
    maxDiff = None

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

    def _dump_and_load(self, expected_objects, not_expected_objects=None, doc_to_doc_class=None):
        output_stream = StringIO()
        CouchDataDumper(self.domain_name, []).dump(output_stream)

        self._delete_couch_data()

        # make sure that there's no data left in the DB
        objects_remaining = _get_doc_counts_from_db(self.domain_name)
        self.assertEqual({}, objects_remaining, 'Not all data deleted: {}'.format(objects_remaining))

        dump_output = output_stream.getvalue().split('\n')
        dump_lines = [line.strip() for line in dump_output if line.strip()]

        with mock_out_couch() as fake_db:
            total_object_count, loaded_object_count = CouchDataLoader().load_objects(dump_lines)

        def _dump_line_to_doc_class(line):
            doc = json.loads(line)
            return _doc_to_doc_class(doc, doc_to_doc_class)

        actual_model_counts = Counter([
            _dump_line_to_doc_class(line)
            for line in dump_lines
        ])
        expected_object_counts = Counter(
            object.__class__ for object in expected_objects
        )
        expected_total_objects = len(expected_objects)
        self.assertDictEqual(dict(expected_object_counts), dict(actual_model_counts))
        self.assertEqual(expected_total_objects, sum(loaded_object_count.values()))
        self.assertEqual(expected_total_objects, total_object_count)

        counts_in_fake_db = _get_doc_counts_from_fake_db(fake_db, doc_to_doc_class)
        self.assertDictEqual(dict(expected_object_counts), counts_in_fake_db)

        for object in expected_objects:
            copied_object_source = fake_db.get(object._id)
            self.assertDictEqual(object.to_json(), copied_object_source)

        if not_expected_objects:
            for object in not_expected_objects:
                with self.assertRaises(ResourceNotFound):
                    fake_db.get(object._id)

        return fake_db

    def test_docs_with_domain(self):
        # one test for all docs that have a 'domain' property
        doc_types = []
        special_handlers = {
            "DataSourceConfiguration": {
                "referenced_doc_type": lambda x: random.choice(VALID_REFERENCED_DOC_TYPES)
            }
        }
        for provider in DOC_PROVIDERS:
            if isinstance(provider, DocTypeIDProvider):
                doc_types.extend(provider.doc_types)

        def _make_doc(doc_type, domain):
            doc_class = get_document_class_by_doc_type(doc_type)
            properties_by_key = doc_class._properties_by_key
            self.assertIn('domain', properties_by_key, doc_type)
            doc = doc_class(domain=domain)
            for key, prop in properties_by_key.items():
                if key != 'domain' and prop.required:
                    special_handler = special_handlers.get(doc_type, {})
                    special_handler = special_handler.get(prop.name)
                    if special_handler:
                        doc[key] = special_handler(prop)
                    else:
                        doc[key] = _get_property_value(prop)

            doc = doc_class.wrap(doc.to_json())  # dump and wrap to set default props etc.
            res = doc_class.get_db().save_doc(doc)
            self.assertTrue(res['ok'])
            return doc

        expected_docs = []
        not_expected_docs = []
        for doc_type in doc_types:
            expected_docs.append(_make_doc(doc_type, self.domain_name))
            not_expected_docs.append(_make_doc(doc_type, 'other-domain'))

        self._dump_and_load(expected_docs, not_expected_docs)

    def test_multimedia(self):
        from corehq.apps.hqmedia.models import CommCareAudio, CommCareImage, CommCareVideo
        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images', 'commcare-hq-logo.png')
        with open(image_path, 'rb') as f:
            image_data = f.read()

        image = CommCareImage.get_by_data(image_data)
        image.attach_data(image_data, original_filename='logo.png')
        image.add_domain(self.domain_name)
        self.assertEqual(image_data, image.get_display_file(False))

        audio_data = b'fake audio data'
        audio = CommCareAudio.get_by_data(audio_data)
        audio.attach_data(audio_data, original_filename='tr-la-la.mp3')
        audio.add_domain(self.domain_name)
        self.assertEqual(audio_data, audio.get_display_file(False))

        video_data = b'fake video data'
        video = CommCareVideo.get_by_data(video_data)
        video.attach_data(video_data, 'kittens.mp4')
        video.add_domain(self.domain_name)
        self.assertEqual(video_data, video.get_display_file(False))

        fakedb = self._dump_and_load([image, audio, video])

        copied_image = CommCareImage.wrap(fakedb.get(image._id))
        copied_audio = CommCareAudio.wrap(fakedb.get(audio._id))
        copied_video = CommCareVideo.wrap(fakedb.get(video._id))
        self.assertEqual(image_data, copied_image.get_display_file(False))
        self.assertEqual(audio_data, copied_audio.get_display_file(False))
        self.assertEqual(video_data, copied_video.get_display_file(False))

    def test_web_user(self):
        from corehq.apps.users.models import WebUser
        other_domain = Domain(name='other-domain')
        other_domain.save()
        self.addCleanup(other_domain.delete)

        web_user = WebUser.create(
            domain=self.domain_name,
            username='webuser_1',
            password='secret',
            created_by=None,
            created_via=None,
            email='webuser1@example.com',
        )
        other_user = WebUser.create(
            domain='other-domain',
            username='other_webuser',
            password='secret',
            created_by=None,
            created_via=None,
            email='webuser2@example.com',
        )

        self._dump_and_load([web_user], [other_user])


class TestDumpLoadToggles(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDumpLoadToggles, cls).setUpClass()
        cls.domain_name = uuid.uuid4().hex

    def setUp(self):
        super(TestDumpLoadToggles, self).setUp()
        self.mocked_toggles, self.expected_items = self._get_mocked_toggles()

    def tearDown(self):
        for toggle in self.mocked_toggles.values():
            toggle.bust_cache()
        super(TestDumpLoadToggles, self).tearDown()

    def test_dump_toggles(self):
        dumper = ToggleDumper(self.domain_name, [])
        dumper._user_ids_in_domain = Mock(return_value={'user1', 'user2', 'user3'})

        output_stream = StringIO()

        with mock_out_couch(docs=[doc.to_json() for doc in self.mocked_toggles.values()]):
            dumper.dump(output_stream)
        output_stream.seek(0)
        lines = output_stream.readlines()
        dumped = [json.loads(line.strip()) for line in lines]
        self.assertEqual(len(dumped), 3, ','.join([d['slug'] for d in dumped]))
        for dump in dumped:
            self.assertItemsEqual(self.expected_items[dump['slug']], dump['enabled_users'])

    def _get_mocked_toggles(self):
        from toggle.models import generate_toggle_id
        from toggle.models import Toggle
        from toggle.shortcuts import namespaced_item

        mocked_toggles = {
            toggle.slug: Toggle(_id=generate_toggle_id(toggle.slug), slug=toggle.slug)
            for toggle in random.sample(all_toggles(), 3)
        }
        toggles = list(mocked_toggles.values())
        domain_item = namespaced_item(self.domain_name, NAMESPACE_DOMAIN)
        toggles[0].enabled_users = [domain_item]
        toggles[1].enabled_users = ['user1', 'other-user', 'user2']
        toggles[2].enabled_users = ['user1', domain_item, namespaced_item('other_domain', NAMESPACE_DOMAIN)]

        expected_items = {
            toggles[0].slug: [domain_item],
            toggles[1].slug: ['user1', 'user2'],
            toggles[2].slug: ['user1', domain_item],
        }

        return mocked_toggles, expected_items

    def test_load_toggles(self):
        from toggle.models import Toggle

        dumped_data = [
            json.dumps(Toggle(slug=slug, enabled_users=items).to_json())
            for slug, items in self.expected_items.items()
        ]

        existing_toggle_docs = []
        for toggle in self.mocked_toggles.values():
            doc_dict = toggle.to_json()
            expected = self.expected_items[toggle.slug]
            # leave only items that aren't in the dump
            doc_dict['enabled_users'] = [item for item in doc_dict['enabled_users'] if item not in expected]
            existing_toggle_docs.append(doc_dict)

        with mock_out_couch(docs=existing_toggle_docs):
            ToggleLoader().load_objects(dumped_data)

            for mocked_toggle in self.mocked_toggles.values():
                loaded_toggle = Toggle.get(mocked_toggle.slug)
                self.assertItemsEqual(mocked_toggle.enabled_users, loaded_toggle.enabled_users)


def _get_doc_counts_from_db(domain):
    return {
        get_model_label(doc_class): len(doc_ids)
        for doc_class, doc_ids in get_doc_ids_to_dump(domain) if doc_ids
    }


def _get_doc_counts_from_fake_db(fake_db, doc_to_doc_class=None):
    return dict(Counter(
        _doc_to_doc_class(doc, doc_to_doc_class)
        for doc in fake_db.mock_docs.values()
    ))


def _doc_to_doc_class(doc, doc_to_doc_class):
    if doc_to_doc_class:
        doc_class = doc_to_doc_class(doc)
        if doc_class:
            return doc_class
    return get_document_class_by_doc_type(doc['doc_type'])


def _get_property_value(prop):
    from jsonobject import properties
    import random
    import string
    return {
        properties.StringProperty: lambda: ''.join(random.choice(string.ascii_uppercase) for _ in range(10)),
    }[prop.__class__]()
