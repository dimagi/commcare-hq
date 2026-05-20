import os
import tempfile
from contextlib import contextmanager
from unittest import mock

from django.core.management import call_command


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
