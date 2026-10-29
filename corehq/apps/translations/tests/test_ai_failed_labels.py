import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.translations.app_translations.ai_failed_labels import (
    failed_label_reason,
    get_failed_labels,
    save_failed_labels,
)
from corehq.blobs import CODES
from corehq.blobs.tests.fixtures import blob_db

DOMAIN = 'test-failed-labels'
APP_ID = 'app-id'
RECORD = {'reason': 'empty', 'source': 'What is the name?', 'type': 'form_text',
          'unique_id': 'form-id', 'itext_id': 'name-label'}
OTHER_RECORD = {**RECORD, 'reason': 'no_translation'}


class TestFailedLabels(TestCase):

    def setUp(self):
        super().setUp()
        self.db = blob_db()

    def test_no_list_before_a_run(self):
        assert get_failed_labels(APP_ID, 'fra') is None

    def test_next_run_replaces_the_list(self):
        save_failed_labels(DOMAIN, APP_ID, 'fra', [RECORD])

        save_failed_labels(DOMAIN, APP_ID, 'fra', [OTHER_RECORD])

        assert get_failed_labels(APP_ID, 'fra') == [OTHER_RECORD]
        assert len(self.db.metadb.get_for_parent(APP_ID, CODES.ai_translation_failed_labels)) == 1

    def test_run_with_no_failures_removes_the_list(self):
        save_failed_labels(DOMAIN, APP_ID, 'fra', [RECORD])

        save_failed_labels(DOMAIN, APP_ID, 'fra', [])

        assert get_failed_labels(APP_ID, 'fra') is None

    def test_languages_keep_their_own_lists(self):
        save_failed_labels(DOMAIN, APP_ID, 'fra', [RECORD])

        save_failed_labels(DOMAIN, APP_ID, 'hin', [OTHER_RECORD])

        assert get_failed_labels(APP_ID, 'fra') == [RECORD]
        assert get_failed_labels(APP_ID, 'hin') == [OTHER_RECORD]

    def test_list_is_gone_once_it_expires(self):
        save_failed_labels(DOMAIN, APP_ID, 'fra', [RECORD])
        # the cleanup task hasn't deleted it yet
        [meta] = self.db.metadb.get_for_parent(APP_ID, CODES.ai_translation_failed_labels)
        meta.expires_on = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        meta.save()

        assert get_failed_labels(APP_ID, 'fra') is None

    @patch('corehq.apps.translations.app_translations.ai_failed_labels.MAX_FAILED_LABELS', 2)
    def test_keeps_only_the_first_labels(self):
        third_record = {**RECORD, 'source': 'How old are you?'}

        save_failed_labels(DOMAIN, APP_ID, 'fra', [RECORD, OTHER_RECORD, third_record])

        assert get_failed_labels(APP_ID, 'fra') == [RECORD, OTHER_RECORD]

    def test_list_deleted_after_its_metadata_was_read(self):
        save_failed_labels(DOMAIN, APP_ID, 'fra', [RECORD])
        # as if a newer run deleted it between reading the metadata and the list
        [meta] = self.db.metadb.get_for_parent(APP_ID, CODES.ai_translation_failed_labels)
        os.remove(self.db.get_path(meta.key))

        assert get_failed_labels(APP_ID, 'fra') is None


def test_reason_for_a_code_this_release_doesnt_know():
    # e.g. stored by a later release, or by an earlier one that had it
    assert failed_label_reason('some_old_code') == "The label couldn't be translated."
