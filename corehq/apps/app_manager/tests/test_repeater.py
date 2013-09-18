from datetime import datetime

# Introduced in Django 1.4, but we are on 1.3 # from django.utils.timezone import now
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client

from corehq.apps.receiverwrapper.models import RepeatRecord, AppStructureRepeater
from corehq.apps.app_manager.models import Application

class TestAppStructureRepeater(TestCase):
    def setUp(self):
        self.client = Client()
        self.domain = 'bedazzled'
        self.forwarding_url = 'http://not-a-real-url-at-all'

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
        
        
