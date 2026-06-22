import os
import tempfile
from contextlib import contextmanager
from unittest import mock

import pytest
from django.core.management import call_command
from django.conf import settings
from django.test import override_settings

from corehq.blobs.management.commands.run_blob_export import _ensure_s3_pool_size


@pytest.mark.parametrize("s3_settings, concurrency, expected", [
    ({'url': 'x'}, 25, 25),                             # no pool set -> raise to concurrency
    ({'url': 'x'}, 10, None),                           # at the default -> leave config unset
    ({'config': {'max_pool_connections': 50}}, 25, 50),  # larger configured pool -> kept
    ({'config': {'max_pool_connections': 5}}, 25, 25),   # smaller configured pool -> raised
])
def test_ensure_s3_pool_size(s3_settings, concurrency, expected):
    with override_settings(S3_BLOB_DB_SETTINGS=s3_settings, OLD_S3_BLOB_DB_SETTINGS=None):
        _ensure_s3_pool_size(concurrency)
        config = settings.S3_BLOB_DB_SETTINGS.get('config')
        if expected is None:
            assert config is None or 'max_pool_connections' not in config
        else:
            assert config['max_pool_connections'] == expected


def test_ensure_s3_pool_size_without_s3_configured_is_noop():
    with override_settings(S3_BLOB_DB_SETTINGS=None, OLD_S3_BLOB_DB_SETTINGS=None):
        _ensure_s3_pool_size(25)  # must not raise


@contextmanager
def chdir(path):
    """Change cwd within a block, restoring on exit."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


class TestRunBlobExportDirFlag:
    """Tests for the --dir flag on the run_blob_export command.

    ``BlobExporter`` is mocked so the test does not depend on the blob DB.
    """

    def test_creates_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'nested', 'subdir')
            assert not os.path.exists(target)

            with mock.patch(
                'corehq.blobs.management.commands.run_blob_export.BlobExporter'
            ) as mock_exporter:
                mock_exporter.return_value.migrate.return_value = (0, 0)
                call_command('run_blob_export', 'mydomain', dir=target)

            assert os.path.isdir(target)
            export_filename = mock_exporter.return_value.migrate.call_args.args[0]
            assert export_filename.startswith(target + os.sep)

    def test_no_dir_writes_to_cwd(self):
        with tempfile.TemporaryDirectory() as tmp, chdir(tmp):
            with mock.patch(
                'corehq.blobs.management.commands.run_blob_export.BlobExporter'
            ) as mock_exporter:
                mock_exporter.return_value.migrate.return_value = (0, 0)
                call_command('run_blob_export', 'mydomain')

            export_filename = mock_exporter.return_value.migrate.call_args.args[0]
            assert os.sep not in export_filename
