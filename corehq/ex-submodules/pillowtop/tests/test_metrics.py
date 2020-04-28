import uuid

from django.test import SimpleTestCase, override_settings

from corehq.util.metrics.tests.utils import capture_metrics
from pillowtop.feed.interface import Change, ChangeMeta
from pillowtop.tests.test_import_pillows import FakePillow


class TestPillowMetrics(SimpleTestCase):
    maxDiff = None

    def _get_metrics(self, changes, batch=False):
        pillow = FakePillow()
        with capture_metrics() as metrics:
            if batch:
                pillow._record_datadog_metrics(changes, 5)
            else:
                for change in changes:
                    pillow._record_change_in_datadog(change, 2)
        return metrics

    def test_basic_metrics(self):
        metrics = self._get_metrics([self._get_change()])
        self.assertEqual(set(metrics.to_flattened_dict()), {
            'commcare.change_feed.changes.count.datasource:test_commcarehq',
            'commcare.change_feed.changes.count.pillow_name:fake pillow',
            'commcare.change_feed.changes.count.case_type:NA',
            'commcare.change_feed.change_lag.pillow_name:fake pillow',
            'commcare.change_feed.change_lag.topic:case',
            'commcare.change_feed.processing_time.total.pillow_name:fake pillow',
            'commcare.change_feed.processing_time.count.pillow_name:fake pillow',
        })

    def test_basic_metrics_with_partition(self):
        metrics = self._get_metrics([self._get_change_with_partition()])
        self.assertEqual(set(metrics.to_flattened_dict()), {
            'commcare.change_feed.changes.count.datasource:test_commcarehq',
            'commcare.change_feed.changes.count.pillow_name:fake pillow',
            'commcare.change_feed.changes.count.case_type:NA',
            'commcare.change_feed.change_lag.pillow_name:fake pillow',
            'commcare.change_feed.change_lag.topic:case-1',
            'commcare.change_feed.processing_time.total.pillow_name:fake pillow',
            'commcare.change_feed.processing_time.count.pillow_name:fake pillow',
        })

    @override_settings(ENTERPRISE_MODE=True)
    def test_case_type_metrics(self):
        metrics = self._get_metrics([self._get_change()])
        self.assertEqual(metrics.sum('commcare.change_feed.changes.count', case_type='person'), 1)

    @override_settings(ENTERPRISE_MODE=True)
    def test_case_type_metrics_batch(self):
        metrics = self._get_metrics([
            self._get_change(doc_subtype='person'),
            self._get_change(doc_subtype='person'),
            self._get_change(doc_subtype='cat'),
            self._get_change(doc_type='form'),
        ], batch=True)

        self.assertEqual(metrics.sum('commcare.change_feed.changes.count', case_type='person'), 2)
        self.assertEqual(metrics.sum('commcare.change_feed.changes.count', case_type='cat'), 1)

        # extra 1 for the change with a different doc type
        self.assertEqual(metrics.sum('commcare.change_feed.changes.count', pillow_name='fake pillow'), 4)

    def _get_change(self, topic='case', doc_type='CommCareCase', doc_subtype='person'):
        doc_id = uuid.uuid4().hex
        return Change(
            doc_id,
            'seq',
            topic=topic,
            metadata=ChangeMeta(
                data_source_type='couch',
                data_source_name='test_commcarehq',
                document_id=doc_id,
                document_type=doc_type,
                document_subtype=doc_subtype,
                is_deletion=False,

            )
        )

    def _get_change_with_partition(self, topic='case', doc_type='CommCareCase', doc_subtype='person'):
        doc_id = uuid.uuid4().hex
        return Change(
            doc_id,
            'seq',
            topic=topic,
            partition=1,
            metadata=ChangeMeta(
                data_source_type='couch',
                data_source_name='test_commcarehq',
                document_id=doc_id,
                document_type=doc_type,
                document_subtype=doc_subtype,
                is_deletion=False,

            )
        )
