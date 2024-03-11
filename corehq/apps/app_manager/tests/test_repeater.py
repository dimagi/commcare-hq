from datetime import datetime, timedelta

from django.test import TestCase
from django.test.client import Client

from unittest.mock import patch

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.dbaccessors import delete_all_repeat_records
from corehq.motech.repeaters.models import AppStructureRepeater, SQLRepeatRecord


class TestAppStructureRepeater(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        cls.forwarding_url = 'http://not-a-real-url-at-all'

        cls.domain = 'bedazzled'
        cls.domain_obj = Domain.get_or_create_with_name(cls.domain)

        # DATA_FORWARDING is on PRO and above
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.PRO)
        cls.conn = ConnectionSettings.objects.create(url=cls.forwarding_url, domain=cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def tearDown(self):
        delete_all_repeat_records()
        super().tearDown()

    def test_repeat_record_not_created(self):
        """
        When an application without a repeater is saved, then a repeat record should not be created
        """
        self.application = Application(domain=self.domain)
        self.application.save()
        self.addCleanup(self.application.delete)

        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        repeat_records = SQLRepeatRecord.objects.filter(domain=self.domain, next_check__lt=later)
        self.assertEqual(len(repeat_records), 0)

    def test_repeat_record_created(self):
        """
        When an application with a repeater is saved, then a repeat record should be created
        """
        self.app_structure_repeater = AppStructureRepeater(domain=self.domain, connection_settings=self.conn)
        self.app_structure_repeater.save()
        self.addCleanup(self.app_structure_repeater.delete)

        self.application = Application(domain=self.domain)
        self.application.save()
        self.addCleanup(self.application.delete)

        later = datetime.utcnow() + timedelta(hours=48 + 1)
        repeat_records = SQLRepeatRecord.objects.filter(domain=self.domain, next_check__lt=later)
        self.assertEqual(len(repeat_records), 1)

    def test_repeat_record_forwarded(self):
        """
        When an application with a repeater is saved, then HQ should try to forward the repeat record
        """
        self.app_structure_repeater = AppStructureRepeater(domain=self.domain, connection_settings=self.conn)
        self.app_structure_repeater.save()
        self.addCleanup(self.app_structure_repeater.delete)

        with patch('corehq.motech.repeaters.models.simple_request') as mock_fire:
            self.application = Application(domain=self.domain)
            self.application.save()
            self.addCleanup(self.application.delete)

            self.assertEqual(mock_fire.call_count, 1)
