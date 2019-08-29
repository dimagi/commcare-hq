
from datetime import datetime, timedelta

from django.test import TestCase
from django.test.client import Client

from mock import patch

from corehq.apps.app_manager.models import Application
from corehq.motech.repeaters.dbaccessors import delete_all_repeat_records
from corehq.motech.repeaters.models import AppStructureRepeater, RepeatRecord


class TestAppStructureRepeater(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestAppStructureRepeater, cls).setUpClass()
        cls.client = Client()
        cls.domain = 'bedazzled'
        cls.forwarding_url = 'http://not-a-real-url-at-all'

    def tearDown(self):
        delete_all_repeat_records()

    def test_repeat_record_not_created(self):
        """
        When an application without a repeater is saved, then a repeat record should not be created
        """
        self.application = Application(domain=self.domain)
        self.application.save()
        self.addCleanup(self.application.delete)

        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        repeat_records = RepeatRecord.all(domain=self.domain, due_before=later)
        self.assertEqual(len(repeat_records), 0)

    def test_repeat_record_created(self):
        """
        When an application with a repeater is saved, then a repeat record should be created
        """
        self.app_structure_repeater = AppStructureRepeater(domain=self.domain, url=self.forwarding_url)
        self.app_structure_repeater.save()
        self.addCleanup(self.app_structure_repeater.delete)

        self.application = Application(domain=self.domain)
        self.application.save()
        self.addCleanup(self.application.delete)

        later = datetime.utcnow() + timedelta(hours=48 + 1)
        repeat_records = RepeatRecord.all(domain=self.domain, due_before=later)
        self.assertEqual(len(repeat_records), 1)

    def test_repeat_record_forwarded(self):
        """
        When an application with a repeater is saved, then HQ should try to forward the repeat record
        """
        self.app_structure_repeater = AppStructureRepeater(domain=self.domain, url=self.forwarding_url)
        self.app_structure_repeater.save()
        self.addCleanup(self.app_structure_repeater.delete)

        with patch('corehq.motech.repeaters.models.simple_post') as mock_fire:
            self.application = Application(domain=self.domain)
            self.application.save()
            self.addCleanup(self.application.delete)

            self.assertEqual(mock_fire.call_count, 1)
