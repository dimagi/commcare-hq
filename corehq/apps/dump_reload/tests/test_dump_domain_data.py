import os
import tempfile
import zipfile
from contextlib import contextmanager

from django.core.management import call_command

from corehq.apps.dump_reload.management.commands.dump_domain_data import (
    _get_dump_stream_filename,
)


@contextmanager
def chdir(path):
    """Change cwd within a block, restoring on exit."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


class TestGetDumpStreamFilename:
    def test_without_path(self):
        assert _get_dump_stream_filename('sql', 'mydomain', '2026-05-18') == \
            'dump-sql-mydomain-2026-05-18.gz'

    def test_with_path(self):
        assert _get_dump_stream_filename('sql', 'mydomain', '2026-05-18', path='/tmp/out') == \
            '/tmp/out/dump-sql-mydomain-2026-05-18.gz'


class TestDumpDomainDataDirFlag:
    """Tests for the --dir flag on the dump_domain_data command.

    Passes ``--dumper=__none__`` so no dumpers run — this avoids needing a
    real database while still exercising the directory-handling code path
    and verifying the final zip lands in the requested directory.
    """

    def test_creates_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'nested', 'subdir')
            assert not os.path.exists(target)

            call_command(
                'dump_domain_data',
                'mydomain',
                dir=target,
                dumpers=['__none__'],
            )

            assert os.path.isdir(target)
            zips = [f for f in os.listdir(target) if f.endswith('.zip')]
            assert len(zips) == 1
            with zipfile.ZipFile(os.path.join(target, zips[0])) as z:
                assert z.namelist() == ['meta.json']

    def test_dir_skipped_in_console_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            unused = os.path.join(tmp, 'not-created')
            call_command(
                'dump_domain_data',
                'mydomain',
                dir=unused,
                console=True,
                dumpers=['__none__'],
            )
            assert not os.path.exists(unused)

    def test_no_dir_writes_to_cwd(self):
        with tempfile.TemporaryDirectory() as tmp, chdir(tmp):
            call_command(
                'dump_domain_data',
                'mydomain',
                dumpers=['__none__'],
            )
            zips = [f for f in os.listdir(tmp) if f.endswith('.zip')]
            assert len(zips) == 1
