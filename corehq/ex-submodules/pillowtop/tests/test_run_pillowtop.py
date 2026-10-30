from unittest.mock import patch

import pytest
from testil import Config
from unmagic import fixture

from ..run_pillowtop import (
    restart_exited_processes,
    run_pillow_by_name,
    start_pillows,
)


def test_run_pillow_by_name_single_process():
    started = patch_pillow_starter()
    run_pillow_by_name(
        pillow_name='fake',
        num_processes=1,
        process_number=0,
        processor_chunk_size=100,
        dedicated_migration_process=False,
        exclude_ucrs=['abc', 'def'],
    )
    assert started == ["worker 0 of 1 exclude_ucrs=['abc', 'def']"]


def test_run_pillow_by_name_dedicated_migration_process():
    started = patch_pillow_starter()
    run_pillow_by_name(
        pillow_name='fake',
        num_processes=1,
        process_number=0,
        processor_chunk_size=100,
        dedicated_migration_process=True,
        exclude_ucrs='',
    )
    assert started == ['migrate 0 of 1']


def test_run_pillow_by_name_with_gevent_workers_migration_process():
    started = patch_pillow_starter()
    run_pillow_by_name(
        pillow_name='fake',
        num_processes=4,
        process_number=0,
        gevent_workers=3,
        processor_chunk_size=100,
        dedicated_migration_process=True,
        exclude_ucrs='',
    )
    assert started == ['migrate 0 of 4']


def test_run_pillow_by_name_with_gevent_workers():
    started = patch_pillow_starter()
    run_pillow_by_name(
        pillow_name='fake',
        num_processes=4,
        process_number=1,
        gevent_workers=3,
        processor_chunk_size=100,
        dedicated_migration_process=True,
        exclude_ucrs='',
    )
    assert started == ['worker 1 of 10', 'worker 2 of 10', 'worker 3 of 10']


def test_run_pillow_by_name_with_gevent_workers_and_no_migration_process():
    started = patch_pillow_starter()
    run_pillow_by_name(
        pillow_name='fake',
        num_processes=4,
        process_number=1,
        gevent_workers=3,
        processor_chunk_size=100,
        dedicated_migration_process=False,
        exclude_ucrs='',
    )
    assert started == ['worker 3 of 12', 'worker 4 of 12', 'worker 5 of 12']


def test_run_pillow_by_name_with_gevent_workers_exclude_ucrs():
    started = patch_pillow_starter()
    run_pillow_by_name(
        pillow_name='fake',
        num_processes=4,
        process_number=0,
        gevent_workers=2,
        processor_chunk_size=100,
        dedicated_migration_process=False,
        exclude_ucrs=['abc'],
    )
    assert started == [
        "worker 0 of 8 exclude_ucrs=['abc']",
        "worker 1 of 8 exclude_ucrs=['abc']",
    ]


@pytest.mark.parametrize("workers", [0, 1, -1])
def test_run_pillow_by_name_with_too_few_gevent_workers(workers):
    started = patch_pillow_starter()
    with pytest.raises(SystemExit):
        run_pillow_by_name(
            pillow_name='fake',
            num_processes=4,
            process_number=1,
            gevent_workers=workers,
            processor_chunk_size=100,
        )
    assert not started


def test_start_pillows_closes_db_connections_before_forking():
    events = patch_processes()
    with patch('pillowtop.run_pillowtop.wait', side_effect=KeyboardInterrupt), pytest.raises(SystemExit):
        start_pillows(fake_pillows('pillow1', 'pillow2'))

    assert events == ['close', 'start pillow1', 'close', 'start pillow2']


def test_start_pillows_restarts_exited_processes():
    events = patch_processes()
    waits = []

    def wait(sentinels):
        waits.append(sorted(sentinels))
        if len(waits) == 1:
            FakeProcess.exited.add('pillow2')
        else:
            raise KeyboardInterrupt  # stop start_pillows looping

    with (
        patch('pillowtop.run_pillowtop.wait', wait),
        patch('pillowtop.run_pillowtop.time.sleep'),
        pytest.raises(SystemExit),
    ):
        start_pillows(fake_pillows('pillow1', 'pillow2'))

    assert waits == [['pillow1', 'pillow2'], ['pillow1', 'pillow2']]
    assert events == ['close', 'start pillow1', 'close', 'start pillow2', 'close', 'start pillow2']


def test_restart_exited_processes():
    events = patch_processes()
    pillows = fake_pillows('pillow1', 'pillow2', 'pillow3')
    processes = [(pillow, FakeProcess(pillow.run)) for pillow in pillows]
    FakeProcess.exited.update({'pillow1', 'pillow3'})

    processes_incl_restarted = restart_exited_processes(processes)

    assert events == ['close', 'start pillow1', 'close', 'start pillow3']
    assert [pillow for pillow, process in processes_incl_restarted] == pillows
    assert processes_incl_restarted[1] == processes[1]  # pillow2 is still running
    assert processes_incl_restarted[0][1] is not processes[0][1]
    assert processes_incl_restarted[2][1] is not processes[2][1]


def fake_pillows(*names):
    return [Config(pillow_id=name, run=lambda name=name: name) for name in names]


class FakeProcess:
    events = None
    exited = None

    def __init__(self, target):
        self.name = self.pid = self.sentinel = target()
        self.exitcode = None

    def start(self):
        self.events.append(f"start {self.name}")
        self.exited.discard(self.name)

    def is_alive(self):
        return self.name not in self.exited


@fixture
def patch_processes():
    events = []
    with (
        patch.object(FakeProcess, 'events', events),
        patch.object(FakeProcess, 'exited', set()),
        patch('pillowtop.run_pillowtop.multiprocessing.Process', FakeProcess),
        patch('pillowtop.run_pillowtop.close_db_connections', lambda: events.append('close')),
    ):
        yield events


@fixture
def patch_pillow_starter(exclude_ucrs=None):
    def _get_pillow(name, **args):
        return Config(name=name, **args)

    def _start_pillow(pillow):
        assert pillow.name == 'fake'
        assert pillow.processor_chunk_size == 100
        dmp = pillow.dedicated_migration_process
        worker = "migrate" if dmp and pillow.process_num == 0 else "worker"
        exclude = f" exclude_ucrs={pillow.exclude_ucrs}" if 'exclude_ucrs' in pillow else ""
        started.append(f"{worker} {pillow.process_num} of {pillow.num_processes}{exclude}")

    started = []
    with (
        # bypass run_gevent_worker because it loops forever
        patch('pillowtop.run_pillowtop.run_gevent_worker', run_pillow_by_name),
        patch('pillowtop.run_pillowtop.get_pillow_by_name', _get_pillow),
        patch('pillowtop.run_pillowtop.start_pillow', _start_pillow),
    ):
        yield started
