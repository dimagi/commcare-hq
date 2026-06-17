from unittest import mock

import pytest

from django.db import router
from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.dump_reload.sql import filters as sql_filters
from corehq.apps.dump_reload.sql.filters import (
    CaseIDFilter,
    CaseIDLimitExceeded,
    FilteredModelIteratorBuilder,
    MultimediaBlobMetaFilter,
    SimpleFilter,
)
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.blobs.models import BlobMeta
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.models import CaseTransaction
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.sql_db.util import get_db_alias_for_partitioned_doc, get_db_aliases_for_partitioned_query
from corehq.motech.repeaters.models import Repeater
from corehq.motech.models import ConnectionSettings


class TestUseAllObjectsInModelIteratorBuilder(TestCase):

    def test_default_manager_ignores_deleted_objects(self):
        deleted_repeater = Repeater.objects.create(
            connection_settings=self.conn_settings, domain="test", is_deleted=True
        )
        active_repeater = Repeater.objects.create(connection_settings=self.conn_settings, domain='test')
        filter = FilteredModelIteratorBuilder(
            "repeaters.Repeater", SimpleFilter("domain"), use_all_objects=False
        )
        built_filter = filter.build('test', Repeater, router.db_for_read(Repeater))
        object_ids = [obj.id for iterator in built_filter.iterators() for obj in iterator]
        self.assertTrue(active_repeater.id in object_ids)
        self.assertTrue(deleted_repeater.id not in object_ids)

    def test_using_all_objects_includes_deleted_objects(self):
        deleted_repeater = Repeater.objects.create(
            connection_settings=self.conn_settings, domain="test", is_deleted=True
        )
        active_repeater = Repeater.objects.create(connection_settings=self.conn_settings, domain='test')
        filter = FilteredModelIteratorBuilder(
            "repeaters.Repeater", SimpleFilter("domain"), use_all_objects=True
        )
        built_filter = filter.build('test', Repeater, router.db_for_read(Repeater))
        object_ids = [obj.id for iterator in built_filter.iterators() for obj in iterator]
        self.assertTrue(active_repeater.id in object_ids)
        self.assertTrue(deleted_repeater.id in object_ids)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn_settings = ConnectionSettings.objects.create(
            domain="test", name="example.com", url="https://example.com/forwarding"
        )


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


@sharded
class TestPagingChildModelByParentId(TestCase):
    """Page a case child model over the case__domain join with the seek aimed at
    the parent's case_id (use_fk_index_hint=True), and check the keyset returns
    every transaction exactly once across pages and shards."""
    domain = 'test-paging-child-by-parent-id'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cases = [CaseFactory(cls.domain).create_case() for _ in range(3)]
        cls.addClassCleanup(FormProcessorTestUtils.delete_all_cases_forms_ledgers, cls.domain)

    def test_returns_every_transaction_exactly_once(self):
        builder = FilteredModelIteratorBuilder(
            'form_processor.CaseTransaction',
            SimpleFilter('case__domain'),
            pagination_key=('case_id', 'pk'),
            use_fk_index_hint=True,
        )
        # chunk_size=2 with 3 cases forces paging across the seek boundary
        transactions = [
            txn
            for db_alias in get_db_aliases_for_partitioned_query()
            for iterator in builder.build(self.domain, CaseTransaction, db_alias).iterators(2)
            for txn in iterator
        ]

        assert {txn.case_id for txn in transactions} == {case.case_id for case in self.cases}
        # no dupes; (case_id, id) is the unique key -- id (pk) repeats across shards
        assert len({(txn.case_id, txn.id) for txn in transactions}) == len(transactions)


@sharded
class TestCaseIDFilter(TestCase):
    domain = 'test-caseid-filter'
    other_domain = 'test-caseid-filter-other'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cases = [CaseFactory(cls.domain).create_case() for _ in range(3)]
        cls.other_case = CaseFactory(cls.other_domain).create_case()
        cls.addClassCleanup(FormProcessorTestUtils.delete_all_cases_forms_ledgers, cls.domain)
        cls.addClassCleanup(FormProcessorTestUtils.delete_all_cases_forms_ledgers, cls.other_domain)

    def _ids_across_shards(self, filter_):
        ids = []
        for db_alias in get_db_aliases_for_partitioned_query():
            ids.extend(filter_.get_ids(self.domain, db_alias=db_alias))
        return ids

    def test_get_ids_returns_only_this_domains_case_ids(self):
        found = set(self._ids_across_shards(CaseIDFilter()))
        assert found == {case.case_id for case in self.cases}
        assert self.other_case.case_id not in found

    def test_get_filters_yields_chunked_case_id_in_queries(self):
        chunks = [
            q
            for db_alias in get_db_aliases_for_partitioned_query()
            for q in CaseIDFilter(chunksize=2).get_filters(self.domain, db_alias=db_alias)
        ]
        all_ids = []
        for q in chunks:
            (lookup, ids), = q.children  # Q(case_id__in=[...]) -> [('case_id__in', [...])]
            assert lookup == 'case_id__in'
            assert len(ids) <= 2
            all_ids.extend(ids)
        assert set(all_ids) == {case.case_id for case in self.cases}

    def test_raises_when_a_shard_exceeds_the_cap(self):
        shard = get_db_alias_for_partitioned_doc(self.cases[0].case_id)
        with mock.patch.object(sql_filters, 'MAX_CASE_IDS_PER_SHARD', 0):
            with pytest.raises(CaseIDLimitExceeded):
                CaseIDFilter().get_ids(self.domain, db_alias=shard)

    def test_count_is_none(self):
        assert CaseIDFilter().count(self.domain) is None


def test_dump_builders_with_fk_index_hint_have_a_foreign_key_leading_key():
    """Guard the dump config: every builder that sets use_fk_index_hint must have a
    leading pagination key backed by a foreign key (so the parent column can be
    derived). Otherwise it would raise at dump time."""
    from corehq.apps.dump_reload.sql.dump import APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP
    from corehq.apps.dump_reload.util import get_model_class
    from corehq.util.queries import _fk_index_column

    builders = [
        builder
        for builders in APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP.values()
        for builder in builders
        if builder.use_fk_index_hint
    ]
    assert builders, "expected some dump builders to set use_fk_index_hint"
    for builder in builders:
        _, model_cls = get_model_class(builder.model_label)
        # raises ValueError unless pagination_key[0] is a foreign key's column
        _fk_index_column(model_cls, builder.pagination_key)
