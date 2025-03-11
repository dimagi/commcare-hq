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
    TEST_LOG_FILE = 'test_deleted_keys_log.ndjson'
    TEST_IDS_FILE = 'test_ids_with_empty_keys.json'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.command = Command()
        cls.command.log_file = cls.TEST_LOG_FILE
        cls.command.ids_file = cls.TEST_IDS_FILE

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
        with open(self.TEST_LOG_FILE, 'r') as log_file:
            log_entries = [json.loads(line) for line in log_file]
            print(log_entries)
            assert any(
                entry['app_id'] == app._id
                and entry['path'] == '/random_field'
                and entry['value'] == {'other_key': 'another_val'}
                for entry in log_entries
            )

    def test_rollback_changes(self):
        app = Application.new_app('test-domain', 'Test App')
        app.random_field = {'': 'some_val', 'other_field': 'some_val'}
        app.nested_field = {'nested': {'': 'nested_val'}}
        app.save()
        self.addCleanup(app.delete)
        self._send_to_es(app)

        self.command.write_ids_to_file([app._id])
        self.command.fix_documents([app._id])

        app_fixed = Application.get(app._id)
        assert '' not in app_fixed.random_field
        assert '' not in app_fixed.nested_field['nested']

        self.command.rollback_changes()

        app_restored = Application.get(app._id)
        assert '' in app_restored.random_field
        assert app_restored.random_field[''] == 'some_val'
        assert '' in app_restored.nested_field['nested']
        assert app_restored.nested_field['nested'][''] == 'nested_val'

    def test_rollback_with_array(self):
        app = Application.new_app('test-domain', 'Test App')
        app.array_field = [
            {'': 'array_val_1'},
            {'normal': 'value', '': 'array_val_2'}
        ]
        app.save()
        self.addCleanup(app.delete)
        self._send_to_es(app)

        self.command.write_ids_to_file([app._id])
        self.command.fix_documents([app._id])

        app_fixed = Application.get(app._id)
        assert '' not in app_fixed.array_field[0]
        assert '' not in app_fixed.array_field[1]

        self.command.rollback_changes()

        app_restored = Application.get(app._id)
        assert '' in app_restored.array_field[0]
        assert app_restored.array_field[0][''] == 'array_val_1'
        assert '' in app_restored.array_field[1]
        assert app_restored.array_field[1][''] == 'array_val_2'

    def test_two_step_process(self):
        app = Application.new_app('test-domain', 'Test App')
        app.random_field = {'': 'some_val', 'other_field': 'some_val'}
        app.save()
        self.addCleanup(app.delete)
        self._send_to_es(app)

        # Step 1: Find documents with empty keys
        ids_with_empty_keys = self.command.find_docs_with_empty_keys()
        self.command.write_ids_to_file(ids_with_empty_keys)

        # Verify IDs file contains the app ID
        with open(self.TEST_IDS_FILE, 'r') as ids_file:
            saved_ids = json.load(ids_file)
            assert app._id in saved_ids

        # Step 2: Fix documents using the IDs file
        self.command.fix_documents(saved_ids)

        # Verify empty keys are removed
        app_fixed = Application.get(app._id)
        assert '' not in app_fixed.random_field
        assert 'other_field' in app_fixed.random_field

        # Verify log file contains the correct entry
        with open(self.TEST_LOG_FILE, 'r') as log_file:
            log_entries = [json.loads(line) for line in log_file]
            assert any(
                entry['app_id'] == app._id
                and entry['path'] == '/random_field'
                and entry['value'] == 'some_val'
                for entry in log_entries
            )

    def test_handle_with_find_only_option(self):
        app = Application.new_app('test-domain', 'Test App')
        app.random_field = {'': 'some_val'}
        app.save()
        self.addCleanup(app.delete)
        self._send_to_es(app)

        # Run the command with find-only option
        command = Command()
        command.log_file = self.TEST_LOG_FILE
        command.ids_file = self.TEST_IDS_FILE
        command.handle(
            find_only=True,
            rollback=False,
            fix_only=False,
            log_file=self.TEST_LOG_FILE,
            ids_file=self.TEST_IDS_FILE
        )

        with open(self.TEST_IDS_FILE, 'r') as ids_file:
            saved_ids = json.load(ids_file)
            assert app._id in saved_ids

        # Verify the app still has the empty key (not fixed)
        app_reloaded = Application.get(app._id)
        assert '' in app_reloaded.random_field

    def test_handle_with_fix_only_option(self):
        app = Application.new_app('test-domain', 'Test App')
        app.random_field = {'': 'some_val'}
        app.save()
        self.addCleanup(app.delete)
        self._send_to_es(app)

        # First, find and save IDs
        command = Command()
        command.log_file = self.TEST_LOG_FILE
        command.ids_file = self.TEST_IDS_FILE
        command.handle(
            find_only=True,
            rollback=False,
            fix_only=False,
            log_file=self.TEST_LOG_FILE,
            ids_file=self.TEST_IDS_FILE
        )

        # Then run the command with fix-only option
        command.handle(
            fix_only=True,
            find_only=False,
            rollback=False,
            log_file=self.TEST_LOG_FILE,
            ids_file=self.TEST_IDS_FILE
        )

        # Verify the app no longer has the empty key
        app_fixed = Application.get(app._id)
        assert '' not in app_fixed.random_field

    def tearDown(self):
        with open(self.TEST_LOG_FILE, 'w') as log_file:
            log_file.truncate()
        with open(self.TEST_IDS_FILE, 'w') as ids_file:
            ids_file.truncate()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if os.path.exists(cls.TEST_LOG_FILE):
            os.remove(cls.TEST_LOG_FILE)
        if os.path.exists(cls.TEST_IDS_FILE):
            os.remove(cls.TEST_IDS_FILE)
