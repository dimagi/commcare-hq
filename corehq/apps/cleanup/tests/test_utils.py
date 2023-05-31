from datetime import datetime

from django.test import TestCase

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.models import Application
from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.cleanup.utils import (
    DeletedDomains,
    hard_delete_couch_docs_before_cutoff,
    hard_delete_sql_objects_before_cutoff,
    migrate_to_deleted_on,
)
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import ReportConfiguration
from corehq.messaging.scheduling.models import AlertSchedule


class TestDeletedDomains(TestCase):

    def test_is_domain_deleted_returns_true_for_deleted_domain(self):
        self.assertTrue(
            DeletedDomains().is_domain_deleted(self.deleted_domain.name))

    def test_is_domain_deleted_returns_false_for_active_domain(self):
        self.assertFalse(
            DeletedDomains().is_domain_deleted(self.active_domain.name))

    def test_is_domain_deleted_returns_false_for_inactive_domain(self):
        self.assertFalse(
            DeletedDomains().is_domain_deleted(self.inactive_domain.name))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.active_domain = create_domain('active', active=True)
        cls.addClassCleanup(cls.active_domain.delete)
        cls.inactive_domain = create_domain('inactive', active=False)
        cls.addClassCleanup(cls.inactive_domain.delete)
        cls.deleted_domain = create_domain('deleted', active=False)
        cls.deleted_domain.delete(leave_tombstone=True)
        cls.addClassCleanup(cls.deleted_domain.delete)


class TestMigrateToDeletedOn(TestCase):

    def test_deleted_on_is_set_if_object_is_deleted(self):
        rule = AutomaticUpdateRule.objects.create(domain='test', deleted=True)
        self.assertIsNone(rule.deleted_on)
        migrate_to_deleted_on(AutomaticUpdateRule, 'deleted', should_audit=True)
        self.assertIsNotNone(AutomaticUpdateRule.objects.get(id=rule.id).deleted_on)

    def test_deleted_on_is_not_set_if_object_is_not_deleted(self):
        rule = AutomaticUpdateRule.objects.create(domain='test')
        self.assertIsNone(rule.deleted_on)
        migrate_to_deleted_on(AutomaticUpdateRule, 'deleted', should_audit=True)
        self.assertIsNone(AutomaticUpdateRule.objects.get(id=rule.id).deleted_on)


class TestHardDeleteSQLObjectsBeforeCutoff(TestCase):

    def test_object_is_hard_deleted_if_deleted_on_is_before_cutoff(self):
        obj = AlertSchedule.objects.create(domain=self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        hard_delete_sql_objects_before_cutoff(self.cutoff)

        with self.assertRaises(AlertSchedule.DoesNotExist):
            AlertSchedule.objects.get(schedule_id=obj.schedule_id)

    def test_object_is_not_hard_deleted_if_deleted_on_is_cutoff(self):
        obj = AlertSchedule.objects.create(domain=self.domain, deleted_on=self.cutoff)

        hard_delete_sql_objects_before_cutoff(self.cutoff)

        self.assertIsNotNone(AlertSchedule.objects.get(schedule_id=obj.schedule_id))

    def test_object_is_not_hard_deleted_if_deleted_on_is_after_cutoff(self):
        obj = AlertSchedule.objects.create(domain=self.domain, deleted_on=datetime(2020, 1, 1, 12, 31))

        hard_delete_sql_objects_before_cutoff(self.cutoff)

        self.assertIsNotNone(AlertSchedule.objects.get(schedule_id=obj.schedule_id))

    def test_object_is_not_hard_deleted_if_deleted_on_is_null(self):
        obj = AlertSchedule.objects.create(domain=self.domain, deleted_on=None)

        hard_delete_sql_objects_before_cutoff(self.cutoff)

        self.assertIsNotNone(AlertSchedule.objects.get(schedule_id=obj.schedule_id))

    def test_audited_object_is_hard_deleted_successfully(self):
        obj = AutomaticUpdateRule.objects.create(domain=self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        hard_delete_sql_objects_before_cutoff(self.cutoff)

        with self.assertRaises(AutomaticUpdateRule.DoesNotExist):
            AutomaticUpdateRule.objects.get(id=obj.id)

    def test_returns_deleted_counts(self):
        deleted_on = datetime(2020, 1, 1, 12, 29)
        for table in [AutomaticUpdateRule, AlertSchedule]:
            table.objects.create(domain=self.domain, deleted_on=deleted_on)

        counts = hard_delete_sql_objects_before_cutoff(self.cutoff)

        self.assertEqual(counts, {'data_interfaces.AutomaticUpdateRule': 1, 'scheduling.AlertSchedule': 1})

    def setUp(self):
        self.domain = 'test_hard_delete_sql_objects_before_cutoff'
        self.cutoff = datetime(2020, 1, 1, 12, 30)


class TestHardDeleteCouchDocsBeforeCutoff(TestCase):

    def test_doc_is_hard_deleted_if_deleted_on_is_before_cutoff(self):
        app = Application(domain=self.domain, name='before-cutoff-app')
        app.save()
        sql_obj = DeletedCouchDoc.objects.create(doc_id=app._id,
                                                 doc_type="Application",
                                                 deleted_on=datetime(2020, 1, 1, 12, 29))

        hard_delete_couch_docs_before_cutoff(self.cutoff)

        with self.assertRaises(ResourceNotFound):
            Application.get_db().get(app._id)

        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(id=sql_obj.id)

    def test_doc_is_not_hard_deleted_if_deleted_on_is_cutoff(self):
        app = Application(domain=self.domain, name='on-cutoff-app')
        app.save()
        sql_obj = DeletedCouchDoc.objects.create(doc_id=app._id,
                                                 doc_type="Application",
                                                 deleted_on=self.cutoff)

        hard_delete_couch_docs_before_cutoff(self.cutoff)

        self.assertIsNotNone(Application.get_db().get(app._id))
        self.assertIsNotNone(DeletedCouchDoc.objects.get(id=sql_obj.id))

    def test_doc_is_not_hard_deleted_if_deleted_on_is_after_cutoff(self):
        app = Application(domain=self.domain, name='after-cutoff-app')
        app.save()
        sql_obj = DeletedCouchDoc.objects.create(doc_id=app._id,
                                                 doc_type="Application",
                                                 deleted_on=datetime(2020, 1, 1, 12, 31))

        hard_delete_couch_docs_before_cutoff(self.cutoff)

        self.assertIsNotNone(Application.get_db().get(app._id))
        self.assertIsNotNone(DeletedCouchDoc.objects.get(id=sql_obj.id))

    def test_doc_is_not_hard_deleted_if_no_deleted_couch_doc_exists(self):
        app = Application(domain=self.domain, name='after-cutoff-app')
        app.save()

        hard_delete_couch_docs_before_cutoff(self.cutoff)

        self.assertIsNotNone(Application.get_db().get(app._id))

    def test_returns_deleted_counts(self):
        deleted_on = datetime(2020, 1, 1, 12, 29)
        app = Application(domain=self.domain, name='after-cutoff-app')
        app.save()
        DeletedCouchDoc.objects.create(doc_id=app._id,
                                       doc_type="Application",
                                       deleted_on=deleted_on)

        report_config = ReportConfiguration(domain=self.domain, config_id='abc123')
        report_config.save()
        DeletedCouchDoc.objects.create(doc_id=report_config._id,
                                       doc_type="ReportConfiguration",
                                       deleted_on=deleted_on)

        counts = hard_delete_couch_docs_before_cutoff(self.cutoff)

        self.assertEqual(counts, {'Application': 1, 'ReportConfiguration': 1})

    def setUp(self):
        self.domain = 'test_hard_delete_couch_docs_before_cutoff'
        self.cutoff = datetime(2020, 1, 1, 12, 30)
