from unittest.mock import Mock, patch

import pytest
from testil import Config

from pillowtop.exceptions import PillowtopCheckpointReset

from ..pillow.interface import ConstructedPillow

cfg = Config(batch=True, changes=[1], chunk_size=1, forever=True)


@pytest.mark.parametrize("cfg, expected_calls", [
    (cfg, [
        "batch [1]",
        "checkpoint 1 seen=1",
    ]),
    (cfg(changes=[1, 2], chunk_size=2), [
        "batch [1, 2]",
        "checkpoint 2 seen=2",
    ]),
    (cfg(changes=[1, None], chunk_size=2), [
        "batch [1]",
        "checkpoint 1 seen=1",
    ]),
    (cfg(changes=[None]), [
        "checkpoint None",
    ]),
    (cfg(changes=[]), []),
    (cfg(changes=[1], chunk_size=2), [
        "batch [1]",
        "checkpoint 1 seen=1",
    ]),
    (cfg(batch=False), [
        "serial 1",
        "checkpoint 1 seen=1",
    ]),
    (cfg(batch=False, changes=[None]), [
        "checkpoint None",
    ]),
    (cfg(forever=False), [
        "batch [1]",
        "checkpoint 1 seen=1",
    ]),
    (cfg(changes=[1, 2], chunk_size=2, forever=False), [
        "batch [1, 2]",
        "checkpoint 2 seen=2",
    ]),
    (cfg(changes=[None], forever=False), [
        "checkpoint None",
    ]),
    (cfg(changes=[1], chunk_size=2, forever=False), [
        "batch [1]",
        "checkpoint 1 seen=1",
    ]),
    (cfg(batch=False, forever=False), [
        "serial 1",
        "checkpoint 1 seen=1",
    ]),
    (cfg(batch=False, changes=[None], forever=False), [
        "checkpoint None",
    ]),
])
def test_process_changes(cfg, expected_calls):
    class feed:
        def iter_changes(**args):
            for change in cfg.changes:
                yield change

    def batch_proc(changes):
        calls.append(f"batch {changes}")

    def serial_proc(change):
        calls.append(f"serial {change}")

    def checkpoint(change, context):
        seen = "" if context is None else f" seen={context.changes_seen}"
        calls.append(f"checkpoint {change}{seen}")

    print(cfg)
    pillow = ConstructedPillow(
        name='TestPillow',
        checkpoint=Mock(),
        change_feed=feed,
        processor=Config(supports_batch_processing=cfg.batch),
        processor_chunk_size=cfg.chunk_size,
    )
    calls = []
    with (
        patch.object(pillow, '_batch_process_with_error_handling', batch_proc),
        patch.object(pillow, 'process_with_error_handling', serial_proc),
        patch.object(pillow, '_record_change_in_datadog'),
        patch.object(pillow, '_record_timeout_in_datadog'),
        patch.object(pillow, '_update_checkpoint', checkpoint),
    ):
        pillow.process_changes(since=None, forever=cfg.forever)
    assert calls == expected_calls


def test_update_checkpoint_on_idle_routes_to_event_handler():
    # An idle/timeout tick (change and context both None) should give the event
    # handler a chance to advance the checkpoint (e.g. flush the consumed Kafka
    # offset), rather than only touching the checkpoint timestamp.
    handler = Mock()
    handler.update_checkpoint_on_idle.return_value = False
    pillow = ConstructedPillow(
        name='TestPillow',
        checkpoint=Mock(),
        change_feed=None,
        processor=None,
        change_processed_event_handler=handler,
    )
    with patch('pillowtop.pillow.interface.cleanup_connections'):
        pillow._update_checkpoint(None, None)
    handler.update_checkpoint_on_idle.assert_called_once_with()
    pillow.checkpoint.touch.assert_not_called()


def test_run_should_continue_on_checkpoint_reset():
    class Stop(Exception):
        pass

    def exception_generator():
        yield PillowtopCheckpointReset
        yield Stop

    def fake_process_changes(*args, **kwargs):
        raise next(exception)

    exception = exception_generator()
    pillow = ConstructedPillow(
        name='TestPillow',
        checkpoint=Mock(),
        change_feed=None,
        processor=None,
    )

    with (
        patch.object(pillow, 'process_changes', fake_process_changes),
        pytest.raises(Stop),
    ):
        pillow.run()
