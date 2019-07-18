from __future__ import absolute_import
from __future__ import unicode_literals

import uuid

from django.test import SimpleTestCase, override_settings

from corehq.util.test_utils import patch_datadog
from pillowtop.feed.interface import Change, ChangeMeta
from pillowtop.tests.test_import_pillows import FakePillow


class TestPillowMetrics(SimpleTestCase):
    maxDiff = None

    def _get_stats(self, changes, batch=False):
        pillow = FakePillow()
        with patch_datadog() as stats:
            if batch:
                pillow._record_datadog_metrics(changes, 5)
            else:
                for change in changes:
                    pillow._record_change_in_datadog(change, 2)
        return stats

    def test_basic_metrics(self):
        stats = self._get_stats([self._get_change()])
        self.assertEqual(set(stats), {
            'commcare.change_feed.changes.count.datasource:test_commcarehq',
            'commcare.change_feed.changes.count.is_deletion:False',
            'commcare.change_feed.changes.count.pillow_name:fake pillow',
            'commcare.change_feed.changes.count.processor:all_processors',
            'commcare.change_feed.change_lag.pillow_name:fake pillow',
            'commcare.change_feed.change_lag.topic:case',
            'commcare.change_feed.processing_time.datasource:test_commcarehq',
            'commcare.change_feed.processing_time.is_deletion:False',
            'commcare.change_feed.processing_time.pillow_name:fake pillow',
            'commcare.change_feed.processing_time.processor:all_processors',
        })

    @override_settings(ENTERPRISE_MODE=True)
    def test_case_type_metrics(self):
        stats = self._get_stats([self._get_change()])
        self.assertIn('commcare.change_feed.changes.count.case_type:person', stats)

    @override_settings(ENTERPRISE_MODE=True)
    def test_case_type_metrics_batch(self):
        stats = self._get_stats([
            self._get_change(doc_subtype='person'),
            self._get_change(doc_subtype='person'),
            self._get_change(doc_subtype='cat'),
            self._get_change(doc_type='form'),
        ], batch=True)

        self.assertEqual(stats['commcare.change_feed.changes.count.case_type:person'], [2])
        self.assertEqual(stats['commcare.change_feed.changes.count.case_type:cat'], [1])

        # extra 1 for the change with a different doc type
        self.assertEqual(stats['commcare.change_feed.changes.count.pillow_name:fake pillow'], [2, 1, 1])

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
