import json
import os

from django.test import TestCase

from corehq.apps.app_manager.management.commands.fix_app_docs_with_empty_keys import (
    Command,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.es import app_adapter
from corehq.apps.es.tests.utils import es_test


@es_test(requires=[app_adapter], setup_class=True)
class TestFixAppDocsWithEmptyKeys(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.command = Command()

    def test_find_docs_with_empty_keys(self):
        app = Application.new_app('test-domain', 'Test App')
        self.addCleanup(app.delete)
        # Adding a random field with an empty key
        # because anything in mappings would throw an error
        # with elasticsearch
        app.random_field = {'': 'some_val'}
        app.save()
        self._send_to_es(app)

        ids_with_empty_keys = self.command.find_docs_with_empty_keys()

        assert app._id in ids_with_empty_keys

    def _send_to_es(self, app):
        app_adapter.index(app, refresh=True)
        self.addCleanup(app_adapter.delete, app._id)

    def test_fix_documents(self):
        app = Application.new_app('test-domain', 'Test App')
        app.random_field = {'': 'some_val', 'other_field': 'some_val'}
        app.save()
        self.addCleanup(app.delete)
        self._send_to_es(app)

        self.command.write_ids_to_file([app._id])
        self.command.fix_documents([app._id])

        # Reload the app and check that empty keys are removed
        app = Application.get(app._id)

        assert 'other_field' in app.random_field
        assert '' not in app.random_field

    def test_log_deleted_keys(self):
        app = Application.new_app('test-domain', 'Test App')
        app.random_field = {
            '': {
                'other_key': 'another_val'
            },
            'other_field': 'some_val'
        }
        app.save()
        self.addCleanup(app.delete)
        self._send_to_es(app)

        self.command.write_ids_to_file([app._id])
        self.command.fix_documents([app._id])

        # Check that the log file contains the correct entry
        with open('deleted_keys_log.ndjson', 'r') as log_file:
            log_entries = [json.loads(line) for line in log_file]
            print(log_entries)
            assert any(
                entry['app_id'] == app._id
                and entry['path'] == '/random_field'
                and json.loads(entry['value']) == {'other_key': 'another_val'}
                for entry in log_entries
            )

    def tearDown(self):
        # Clean up the log file after each test
        with open('deleted_keys_log.ndjson', 'w') as log_file:
            log_file.truncate()
        # Clean up the IDs file after each test
        with open('ids_with_empty_keys.json', 'w') as ids_file:
            ids_file.truncate()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Delete all the files created during test run
        os.remove('deleted_keys_log.ndjson')
        os.remove('ids_with_empty_keys.json')
