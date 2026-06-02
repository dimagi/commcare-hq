import os
import tempfile
import zipfile
from contextlib import contextmanager

import pytest

from django.core.management import call_command
from django.core.management.base import CommandError

from corehq.apps.dump_reload.management.commands.dump_domain_data import (
    Command,
    _get_dump_stream_filename,
    format_dump_stats,
)


class TestFormatDumpStats:
    def test_lists_counts_per_model(self):
        meta = {'sql': {'app.B': 2, 'app.A': 1}, 'couch': {'x.Y': 3}}

        assert format_dump_stats(meta) == [
            f'{"-" * 32} Dump Stats {"-" * 32}',
            'couch',
            f'  {"x.Y":<50}: 3',
            'sql',
            f'  {"app.A":<50}: 1',
            f'  {"app.B":<50}: 2',
            '-' * 76,
            'Dumped 6 objects',
            '-' * 76,
        ]


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

    def test_dir_rejected_in_console_mode(self):
        # The CLI rejects --dir + --console via argparse's mutually
        # exclusive group. Use the parser directly: call_command()
        # bypasses argparse mutex validation for kwargs.
        parser = Command().create_parser('manage.py', 'dump_domain_data')
        with pytest.raises(CommandError, match='not allowed with argument --console'):
            parser.parse_args(['mydomain', '--console', '--dir=/tmp/x'])

    def test_no_dir_writes_to_cwd(self):
        with tempfile.TemporaryDirectory() as tmp, chdir(tmp):
            call_command(
                'dump_domain_data',
                'mydomain',
                dumpers=['__none__'],
            )
            zips = [f for f in os.listdir(tmp) if f.endswith('.zip')]
            assert len(zips) == 1
