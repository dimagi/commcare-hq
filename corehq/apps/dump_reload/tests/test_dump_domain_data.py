import os
import tempfile
import zipfile
from contextlib import contextmanager
from io import StringIO
from unittest import mock

import pytest

from django.core.management import call_command
from django.core.management.base import CommandError

from corehq.apps.dump_reload.management.commands.dump_domain_data import (
    Command,
    _get_dump_stream_filename,
    format_dump_stats,
)


class TestFormatDumpStats:
    def test_with_timing_data_shows_per_model_rate_and_elapsed_totals(self):
        meta = {'sql': {'app.A': 5}}
        timing_data = {'sql': {'total': 0.018, 'models': {'app.A': 0.018}}}

        # 0.018s / 5 rows -> 1.000 h/1M; header and grand total stay elapsed
        assert format_dump_stats(meta, timing_data) == [
            f'{"-" * 32} Dump Stats {"-" * 32}',
            'sql: 0.02s',
            f'  {"app.A":<50}: {5:>10}  1.000h /1M rows',
            '-' * 76,
            'Dumped 5 rows',
            'Total dump time: 0.02s',
            '-' * 76,
        ]

    def test_zero_count_with_a_recorded_time_does_not_divide_by_zero(self):
        meta = {'sql': {'app.Empty': 0}}
        timing_data = {'sql': {'total': 0.1, 'models': {'app.Empty': 0.1}}}

        assert f'  {"app.Empty":<50}: {0:>10}' in format_dump_stats(meta, timing_data)

    def test_model_without_recorded_time_omits_the_time_column(self):
        meta = {'domain': {'Domain': 1}}
        timing_data = {'domain': {'total': 0.5, 'models': {}}}

        assert format_dump_stats(meta, timing_data) == [
            f'{"-" * 32} Dump Stats {"-" * 32}',
            'domain: 0.50s',
            f'  {"Domain":<50}: {1:>10}',
            '-' * 76,
            'Dumped 1 rows',
            'Total dump time: 0.50s',
            '-' * 76,
        ]


class TestSqlChunkSizeFlag:
    @pytest.mark.parametrize('size', ['0', '-500'])
    def test_rejects_a_non_positive_size(self, size):
        parser = Command().create_parser('manage.py', 'dump_domain_data')
        with pytest.raises(CommandError, match='--sql-chunk-size'):
            parser.parse_args(['mydomain', '--sql-chunk-size', size])

    def test_chunk_size_flows_from_the_command_line_to_queryset_iteration(self):
        limits = []

        def capture_limit(queryset, model_class, limit, ignore_ordering=False, pagination_key=('pk',)):
            limits.append(limit)
            return iter([])

        with mock.patch('corehq.apps.dump_reload.sql.filters.queryset_to_iterator', capture_limit):
            call_command(
                'dump_domain_data',
                'mydomain',
                '--sql-chunk-size=1234',
                '--console',
                dumpers=['sql'],
                include=['products.SQLProduct'],
                stdout=StringIO(),
            )

        assert limits and set(limits) == {1234}


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
