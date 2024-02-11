from django.test import TestCase

from corehq.apps.dump_reload.sql.filters import MultimediaBlobMetaFilter
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.blobs.models import BlobMeta
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
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
