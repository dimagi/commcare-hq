from unittest.mock import patch

import pytest
from testil import Config
from unmagic import fixture

from ..run_pillowtop import run_pillow_by_name


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
        patch('pillowtop.run_pillowtop.get_pillow_by_name', _get_pillow),
        patch('pillowtop.run_pillowtop.start_pillow', _start_pillow),
    ):
        yield started
