import json
import os
import random
import uuid
from StringIO import StringIO
from collections import Counter

from datetime import datetime, time

from couchdbkit.exceptions import ResourceNotFound
from django.test import SimpleTestCase
from django.test import TestCase
from fakecouch import FakeCouchDb
from mock import Mock

from corehq.apps.domain.models import Domain
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.couch import CouchDataLoader
from corehq.apps.dump_reload.couch.dump import get_doc_ids_to_dump, ToggleDumper
from corehq.apps.dump_reload.couch.load import ToggleLoader
from corehq.apps.dump_reload.util import get_model_label
from corehq.toggles import all_toggles, NAMESPACE_DOMAIN
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

    def _dump_and_load(self, expected_objects, not_expected_objects=None):
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
        expected_object_counts = Counter(
            object.__class__ for object in expected_objects
        )
        expected_total_objects = len(expected_objects)
        self.assertDictEqual(expected_object_counts, actual_model_counts)
        self.assertEqual(expected_total_objects, sum(loaded_object_count.values()))
        self.assertEqual(expected_total_objects, total_object_count)

        counts_in_fake_db = _get_doc_counts_from_fake_db(fake_db)
        self.assertDictEqual(expected_object_counts, counts_in_fake_db)

        for object in expected_objects:
            copied_object_source = fake_db.get(object._id)
            self.assertDictEqual(object.to_json(), copied_object_source)

        if not_expected_objects:
            for object in not_expected_objects:
                with self.assertRaises(ResourceNotFound):
                    fake_db.get(object._id)

        return fake_db

    def test_location(self):
        from corehq.apps.commtrack.tests.util import make_loc
        loc = make_loc('ct', 'Cape Town', domain=self.domain_name, type='city')
        self._dump_and_load([loc])

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

        self._dump_and_load([app])

    def test_consumption_config(self):
        from corehq.apps.commtrack.models import CommtrackConfig
        from corehq.apps.commtrack.models import ConsumptionConfig

        commtrack_config = CommtrackConfig(
            domain=self.domain.name,
            use_auto_emergency_levels=True
        )
        commtrack_config.consumption_config = ConsumptionConfig(exclude_invalid_periods=True)
        commtrack_config.save()

        self._dump_and_load([commtrack_config])

    def test_default_consumption(self):
        from corehq.apps.consumption.shortcuts import set_default_monthly_consumption_for_domain
        from corehq.apps.consumption.shortcuts import set_default_consumption_for_product
        from corehq.apps.consumption.shortcuts import set_default_consumption_for_supply_point

        objects = [
            set_default_monthly_consumption_for_domain(self.domain_name, 100),
            set_default_consumption_for_product(self.domain_name, 'p1', 42),
            set_default_consumption_for_product(self.domain_name, 'p2', 23),
            set_default_consumption_for_supply_point(self.domain_name, 'p1', 'clinic1', 80)
        ]

        self._dump_and_load(objects)

    def test_multimedia(self):
        from corehq.apps.hqmedia.models import CommCareAudio, CommCareImage, CommCareMultimedia, CommCareVideo
        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'img', 'commcare-hq-logo.png')
        with open(image_path, 'r') as f:
            image_data = f.read()

        image = CommCareImage.get_by_data(image_data)
        image.attach_data(image_data, original_filename='logo.png')
        image.add_domain(self.domain_name)
        self.assertEqual(image_data, image.get_display_file(False))

        audio_data = 'fake audio data'
        audio = CommCareAudio.get_by_data(audio_data)
        audio.attach_data(audio_data, original_filename='tr-la-la.mp3')
        audio.add_domain(self.domain_name)
        self.assertEqual(audio_data, audio.get_display_file(False))

        video_data = 'fake video data'
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

    def test_mobile_auth_keys(self):
        from corehq.apps.mobile_auth.utils import new_key_record
        records = [
            new_key_record(self.domain_name, 'user1'),
            new_key_record(self.domain_name, 'user2'),
        ]
        for r in records:
            r.save()
        other_dom_record = new_key_record('other_domain', 'user1')
        other_dom_record.save()
        self.addCleanup(other_dom_record.delete)

        self._dump_and_load(records, [other_dom_record])

    def test_commtrack(self):
        from corehq.apps.commtrack.tests.util import make_product
        from corehq.apps.commtrack.util import make_program
        program = make_program(self.domain_name, 'program1', 'p1')
        products = [
            make_product(self.domain_name, 'prod_a', 'p_a', 'program1'),
            make_product(self.domain_name, 'prod_b', 'p_b', 'program1'),
        ]
        other_dom_program = make_program('other_doc', 'program2', 'p2')
        other_dom_product = make_product('other_dom', 'prod_c', 'p_c', 'program2')

        expected_docs = products + [program]
        self._dump_and_load(expected_docs, [other_dom_program, other_dom_product])

    def test_reminders(self):
        from corehq.apps.reminders.models import CaseReminderHandler
        from corehq.apps.reminders.models import EVENT_AS_OFFSET
        from corehq.apps.reminders.models import CaseReminderEvent
        from corehq.apps.reminders.models import MATCH_EXACT
        from corehq.apps.reminders.models import CaseReminder

        case_type = 'test_case_type'
        handler = (CaseReminderHandler.create(self.domain_name, 'test')
            .set_case_criteria_start_condition(case_type, 'start_sending', MATCH_EXACT, 'ok')
            .set_case_criteria_start_date(start_offset=1)
            .set_last_submitting_user_recipient()
            .set_sms_content_type('en')
            .set_schedule_manually(
                EVENT_AS_OFFSET,
                3,
                [
                    CaseReminderEvent(
                        day_num=0,
                        fire_time=time(0, 0),
                        message={'en': 'remember to run the migration'},
                        callback_timeout_intervals=[]
                    ),
                ])
            .set_stop_condition(stop_case_property='stop_sending')
            .set_advanced_options()
        )
        handler.save()

        reminder = CaseReminder(
            domain=self.domain_name,
            case_id='test_case_id',
            handler_id=handler._id,
            user_id='user1',
            method=handler.method,
            active=True,
            start_date=datetime.today().date(),
            schedule_iteration_num=1,
            current_event_sequence_num=0,
            callback_try_count=0,
            skip_remaining_timeouts=False,
            sample_id=None,
            xforms_session_ids=[],
        )
        reminder.save()

        self._dump_and_load([handler, reminder])


class TestDumpLoadToggles(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDumpLoadToggles, cls).setUpClass()
        cls.domain_name = uuid.uuid4().hex

    def test_dump_toggles(self):
        mocked_toggles, expected_items = self._get_mocked_toggles()

        dumper = ToggleDumper(self.domain_name, [])
        dumper._user_ids_in_domain = Mock(return_value={'user1', 'user2', 'user3'})

        output_stream = StringIO()

        with mock_out_couch(docs=[doc.to_json() for doc in mocked_toggles.values()]):
            dump_counter = dumper.dump(output_stream)

        self.assertEqual(3, dump_counter['Toggle'])
        output_stream.seek(0)
        dumped = [json.loads(line.strip()) for line in output_stream.readlines()]
        for dump in dumped:
            self.assertItemsEqual(expected_items[dump['slug']], dump['enabled_users'])

    def _get_mocked_toggles(self):
        from toggle.models import generate_toggle_id
        from toggle.models import Toggle
        from toggle.shortcuts import namespaced_item

        mocked_toggles = {
            toggle.slug: Toggle(_id=generate_toggle_id(toggle.slug), slug=toggle.slug)
            for toggle in random.sample(all_toggles(), 3)
        }
        toggles = mocked_toggles.values()
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
        mocked_toggles, expected_items = self._get_mocked_toggles()

        dumped_data = [
            json.dumps(Toggle(slug=slug, enabled_users=items).to_json())
            for slug, items in expected_items.items()
        ]

        existing_toggle_docs = []
        for toggle in mocked_toggles.values():
            doc_dict = toggle.to_json()
            expected = expected_items[toggle.slug]
            # leave only items that aren't in the dump
            doc_dict['enabled_users'] = [item for item in doc_dict['enabled_users'] if item not in expected]
            existing_toggle_docs.append(doc_dict)

        with mock_out_couch(docs=existing_toggle_docs):
            ToggleLoader().load_objects(dumped_data)

            for mocked_toggle in mocked_toggles.values():
                loaded_toggle = Toggle.get(mocked_toggle.slug)
                self.assertItemsEqual(mocked_toggle.enabled_users, loaded_toggle.enabled_users)


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
