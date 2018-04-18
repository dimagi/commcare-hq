from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from django.test import TestCase
from django.test.client import Client

from corehq.motech.repeaters.models import RepeatRecord, AppStructureRepeater
from corehq.apps.app_manager.models import Application


class TestAppStructureRepeater(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestAppStructureRepeater, cls).setUpClass()
        cls.client = Client()
        cls.domain = 'bedazzled'
        cls.forwarding_url = 'http://not-a-real-url-at-all'

    def test_repeat_record_created(self):
        '''
        Tests that whenever an application with a repeater is saved that a repeat record is created.
        '''
        application = Application(domain=self.domain)
        application.save()

        repeat_records = RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())
        self.assertEqual(len(repeat_records), 0)
        
        app_structure_repeater = AppStructureRepeater(domain=self.domain, url=self.forwarding_url)
        app_structure_repeater.save()

        application.save()
        repeat_records = RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

        self.assertEqual(len(repeat_records), 1)
        for repeat_record in repeat_records:
                self.assertEqual(repeat_record.url, self.forwarding_url)
                self.assertEqual(repeat_record.get_payload(), application.get_id)
                repeat_record.delete()
        
        application.delete()
        app_structure_repeater.delete()
