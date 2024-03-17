from datetime import datetime, timedelta

from django.test import TestCase

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.models import (
    Application, DeleteApplicationRecord,
    Module, DeleteModuleRecord,
    DeleteFormRecord,
)
from corehq.apps.casegroups.models import CommCareCaseGroup, DeleteCaseGroupRecord
from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.cleanup.tests.util import _get_delete_record_ids_by_doc_type
from corehq.apps.cleanup.utils import (
    DeletedDomains,
    hard_delete_couch_docs_before_cutoff,
    migrate_to_deleted_on,
)
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group, DeleteGroupRecord


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


class TestHardDeleteCouchDocsBeforeCutoff(TestCase):

    def create_and_delete_test_app(self, soft_delete_app=False):
        app = Application.new_app(self.domain, "TestApp")
        module = app.add_module(Module.new_module("Module", "en"))
        form = app.new_form(module.id, "Form", "en")
        app.save()
        if soft_delete_app:
            app.delete_app()
            app.save()
        return app, module, form

    def test_hard_deletion_deletes_doc_delete_record_sql_doc_application(self):
        app, _, _ = self.create_and_delete_test_app(soft_delete_app=True)
        delete_record_id = _get_delete_record_ids_by_doc_type('DeleteApplicationRecord')[0]

        hard_delete_couch_docs_before_cutoff(datetime.now())

        with self.assertRaises(ResourceNotFound):
            Application.get(app.id)
        with self.assertRaises(ResourceNotFound):
            DeleteApplicationRecord.get(delete_record_id)
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(doc_type=delete_record_id)

    def test_hard_deletion_deletes_doc_delete_record_sql_doc_module(self):
        # Modules are not saved docs but still create an associated DeleteRecord and DeletedCouchDoc
        app, module, _ = self.create_and_delete_test_app()
        app.delete_module(module.unique_id)
        delete_record_id = _get_delete_record_ids_by_doc_type('DeleteModuleRecord')[0]

        hard_delete_couch_docs_before_cutoff(datetime.now())

        with self.assertRaises(ResourceNotFound):
            DeleteModuleRecord.get(delete_record_id)
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(doc_id=delete_record_id)

    def test_hard_deletion_deletes_doc_delete_record_sql_doc_form(self):
        # Forms are not saved docs but still create an associated DeleteRecord and DeletedCouchDoc
        app, module, form = self.create_and_delete_test_app()
        app.delete_form(module.unique_id, form.unique_id)
        delete_record_id = _get_delete_record_ids_by_doc_type('DeleteFormRecord')[0]

        hard_delete_couch_docs_before_cutoff(datetime.now())

        with self.assertRaises(ResourceNotFound):
            DeleteFormRecord.get(delete_record_id)
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(doc_id=delete_record_id)

    def test_hard_deletion_deletes_doc_delete_record_sql_doc_case_group(self):
        case_group = CommCareCaseGroup()
        case_group.save()
        case_group.soft_delete()
        delete_record_id = _get_delete_record_ids_by_doc_type('DeleteCaseGroupRecord')[0]

        hard_delete_couch_docs_before_cutoff(datetime.now())

        with self.assertRaises(ResourceNotFound):
            CommCareCaseGroup.get(case_group._id)
        with self.assertRaises(ResourceNotFound):
            DeleteCaseGroupRecord.get(delete_record_id)
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(doc_id=delete_record_id)

    def test_hard_deletion_deletes_doc_delete_record_sql_doc_group(self):
        group = Group()
        group.save()
        group.soft_delete()
        delete_record_id = _get_delete_record_ids_by_doc_type('DeleteGroupRecord')[0]

        hard_delete_couch_docs_before_cutoff(datetime.now())

        with self.assertRaises(ResourceNotFound):
            Group.get_db().get(group._id)
        with self.assertRaises(ResourceNotFound):
            DeleteGroupRecord.get(delete_record_id)
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(doc_id=delete_record_id)

    def test_doc_is_not_hard_deleted_if_deleted_on_is_cutoff(self):
        app, _, _ = self.create_and_delete_test_app(soft_delete_app=True)
        delete_record_id = _get_delete_record_ids_by_doc_type('DeleteApplicationRecord')[0]
        delete_record = DeleteApplicationRecord.get(delete_record_id)

        hard_delete_couch_docs_before_cutoff(delete_record.datetime)

        self.assertIsNotNone(Application.get_db().get(app.id))
        self.assertIsNotNone(DeleteApplicationRecord.get(delete_record_id))
        self.assertIsNotNone(DeletedCouchDoc.objects.get(doc_id=delete_record_id))

    def test_doc_is_not_hard_deleted_if_deleted_on_is_after_cutoff(self):
        app, _, _ = self.create_and_delete_test_app(soft_delete_app=True)
        delete_record_id = _get_delete_record_ids_by_doc_type('DeleteApplicationRecord')[0]
        delete_record = DeleteApplicationRecord.get(delete_record_id)

        hard_delete_couch_docs_before_cutoff(delete_record.datetime - timedelta(days=2))

        self.assertIsNotNone(Application.get_db().get(app.id))
        self.assertIsNotNone(DeleteApplicationRecord.get(delete_record_id))
        self.assertIsNotNone(DeletedCouchDoc.objects.get(doc_id=delete_record_id))

    def test_doc_is_not_hard_deleted_if_no_deleted_couch_doc_exists(self):
        app, _, _ = self.create_and_delete_test_app()

        hard_delete_couch_docs_before_cutoff(self.cutoff)

        self.assertIsNotNone(Application.get_db().get(app.id))

    def test_returns_deleted_counts(self):
        self.create_and_delete_test_app(soft_delete_app=True)

        counts = hard_delete_couch_docs_before_cutoff(datetime.now())
        self.assertEqual(counts, {'Application': 1})

    def test_doc_is_not_hard_deleted(self):
        app, _, _ = self.create_and_delete_test_app(soft_delete_app=True)
        app.doc_type = app.get_doc_type()
        app.save()
        delete_record_id = _get_delete_record_ids_by_doc_type('DeleteApplicationRecord')[0]

        hard_delete_couch_docs_before_cutoff(self.cutoff)

        self.assertIsNotNone(Application.get_db().get(app.id))
        self.assertIsNotNone(DeleteApplicationRecord.get(delete_record_id))
        self.assertIsNotNone(DeletedCouchDoc.objects.get(doc_id=delete_record_id))

    def setUp(self):
        self.domain = 'test_hard_delete_couch_docs_before_cutoff'
        self.cutoff = datetime(2020, 1, 1, 12, 30)
