from io import StringIO
from unittest.mock import patch

from pillowtop.reindexer.reindexer import Reindexer, ReindexerFactory

from ..management.commands.ptop_reindexer_v2 import (
    FACTORIES_BY_SLUG,
    Command,
)


def test_cleanup_refused_when_reindexer_cannot_clean():
    calls, stderr = run_command(NoCleanReindexer, '--cleanup', '--noinput')
    assert calls == ['exit 1']
    assert 'does not support --cleanup' in stderr


def test_cleanup_cleans_when_reindexer_can_clean():
    calls, stderr = run_command(CleanReindexer, '--cleanup', '--noinput')
    assert calls == ['clean', 'reindex']
    assert stderr == ''


def test_cleanup_refuses_partial_reindex():
    calls, stderr = run_command(PartialReindexer, '--cleanup', '--noinput')
    assert calls == ['exit 1']
    assert 'cannot --cleanup when limited to part of the index' in stderr


def test_partial_reindex_without_cleanup():
    calls, stderr = run_command(PartialReindexer)
    assert calls == ['reindex']
    assert stderr == ''


def test_no_cleanup_does_not_clean():
    calls, stderr = run_command(NoCleanReindexer)
    assert calls == ['reindex']
    assert stderr == ''


def run_command(reindexer_class, *args):
    calls = []

    class Factory(ReindexerFactory):
        slug = 'fake'

        def build(self):
            return reindexer_class(calls)

    stderr = StringIO()
    with patch.dict(FACTORIES_BY_SLUG, {'fake': Factory}):
        command = Command(stderr=stderr)
        try:
            command.run_from_argv(['manage.py', 'ptop_reindexer_v2', 'fake', *args])
        except SystemExit as exc:
            calls.append(f'exit {exc.code}')
    return calls, stderr.getvalue()


class NoCleanReindexer(Reindexer):
    def __init__(self, calls):
        self.calls = calls

    def reindex(self):
        self.calls.append('reindex')


class CleanReindexer(NoCleanReindexer):
    def clean(self):
        self.calls.append('clean')


class PartialReindexer(CleanReindexer):
    partial = True
