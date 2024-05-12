from datetime import datetime

from django.test import TestCase

from corehq.apps.dump_reload.sql.filters import (
    CaseIDFilter,
    MultimediaBlobMetaFilter,
)
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.blobs.models import BlobMeta
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.models.cases import CaseTransaction
from corehq.form_processor.tests.utils import create_case
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


class TestMultimediaBlobMetaFilter(TestCase):

    def test_returns_blobmeta_ids_for_multimedia_attached_to_domain(self):
        multimedia = self.create_multimedia(b'content', domain=self.domain)
        expected_ids = list(
            BlobMeta.objects.partitioned_query(multimedia._id)
            .filter(parent_id=multimedia._id)
            .values_list("id", flat=True)
        )

        filter = MultimediaBlobMetaFilter()
        actual_ids = list(filter.get_ids(self.domain, db_alias=self.db_alias))

        self.assertEqual(actual_ids, expected_ids)

    def test_does_not_return_blobmeta_ids_for_multimedia_outside_of_domain(self):
        self.create_multimedia(b'content', 'different-domain')

        filter = MultimediaBlobMetaFilter()
        actual_ids = list(filter.get_ids(self.domain, db_alias=self.db_alias))

        self.assertEqual(actual_ids, [])

    def test_returns_multiple_blobmeta_ids_if_multiple_attached_to_domain(self):
        multimedia = self.create_multimedia(b'content', domain=self.domain)
        multimedia.attach_data(b'more-content', attachment_id='abc123')
        multimedia.save()  # already set to be cleaned up
        expected_ids = list(
            BlobMeta.objects.partitioned_query(multimedia._id)
            .filter(parent_id=multimedia._id)
            .values_list("id", flat=True)
        )

        filter = MultimediaBlobMetaFilter()
        actual_ids = list(filter.get_ids(self.domain, db_alias=self.db_alias))

        self.assertEqual(len(actual_ids), 2)
        self.assertEqual(actual_ids, expected_ids)

    def create_multimedia(self, content, domain=None):
        multimedia = CommCareMultimedia.get_by_data(content)
        # this will create a BlobMeta object
        multimedia.attach_data(content)
        if domain:
            multimedia.add_domain(domain)
        multimedia.save()
        self.addCleanup(multimedia.delete)
        return multimedia

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = TemporaryFilesystemBlobDB()
        cls.addClassCleanup(cls.db.close)
        cls.domain = 'test-multimedia'
        cls.db_alias = get_db_aliases_for_partitioned_query()[0]


class TestCaseIDFilter(TestCase):
    """
    Given this is used in the context of dumping all data associated with a domain, it is important
    that all cases for a a domain are included in this filter's get_ids method.
    """

    def test_init_raises_exception_if_used_with_model_that_does_not_foreign_key_to_case(self):
        with self.assertRaises(ValueError):
            CaseIDFilter('form_processor.XFormInstance')

    def test_returns_case_ids_for_domain(self):
        create_case('test', case_id='abc123', save=True)
        filter = CaseIDFilter('form_processor.CaseTransaction')
        case_ids = list(filter.get_ids('test', self.db_alias))
        self.assertEqual(case_ids, ['abc123'])

    def test_does_not_return_case_ids_from_other_domain(self):
        create_case('test', case_id='abc123', save=True)
        filter = CaseIDFilter('form_processor.CaseTransaction')
        case_ids = list(filter.get_ids('other', self.db_alias))
        self.assertEqual(case_ids, [])

    def test_deleted_case_ids_are_included(self):
        create_case('test', case_id='abc123', save=True)
        create_case('test', case_id='def456', save=True, deleted=True)
        filter = CaseIDFilter('form_processor.CaseTransaction')
        case_ids = list(filter.get_ids('test', self.db_alias))
        self.assertCountEqual(case_ids, ['abc123', 'def456'])

    def test_count_correctly_counts_all_objects_related_to_case_id(self):
        case1 = create_case('test', case_id='abc123', save=True)
        CaseTransaction.objects.partitioned_query(case1.case_id).create(
            case=case1, server_date=datetime.utcnow(), type=1
        )
        filter = CaseIDFilter('form_processor.CaseTransaction')
        count = filter.count('test')
        self.assertEqual(count, 2)

    def test_count_includes_deleted_cases(self):
        create_case('test', case_id='abc123', save=True)
        create_case('test', case_id='def456', save=True, deleted=True)
        filter = CaseIDFilter('form_processor.CaseTransaction')
        count = filter.count('test')
        self.assertEqual(count, 2)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_alias = get_db_aliases_for_partitioned_query()[0]
