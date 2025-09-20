import multiprocessing
import sys

import gevent

from dimagi.utils.logging import notify_exception

from pillowtop import get_all_pillow_instances
from pillowtop.utils import get_pillow_by_name


def run_pillow_by_name(
    pillow_name,
    *,
    num_processes,
    process_number,
    gevent_workers=None,
    processor_chunk_size,
    dedicated_migration_process=False,
    exclude_ucrs=(),
):
    assert 0 <= process_number < num_processes
    assert processor_chunk_size

    options = {
        'processor_chunk_size': processor_chunk_size,
        'dedicated_migration_process': dedicated_migration_process,
    }
    if exclude_ucrs:
        options['exclude_ucrs'] = exclude_ucrs

    if gevent_workers is not None:
        if gevent_workers < 2:
            sys.exit("cannot run less than 2 gevent workers")
        if process_number > 0 or not dedicated_migration_process:
            if dedicated_migration_process:
                num_processes -= 1
                process_number -= 1
            run_gevent_pillows(pillow_name, num_processes, process_number, gevent_workers, options)
            return
        # the migration process (process_number == 0) is always run in a
        # single process without gevent workers.

    pillow = get_pillow_by_name(
        pillow_name,
        num_processes=num_processes,
        process_num=process_number,
        **options
    )
    start_pillow(pillow)


def run_gevent_pillows(pillow_name, num_processes, process_number, gevent_workers, options):
    # In the case of a dedicated migration process, worker 1 will be
    # assigned partitions 0..N by KafkaChangeFeed._filter_partitions
    # Importantly, no worker will have process_num == 0 when there is
    # a dedicated migration process, so no worker will run migrations.
    assert 'gevent_workers' not in options, options
    offset = 1 if options['dedicated_migration_process'] else 0
    workers = []
    for worker_num in range(gevent_workers):
        workers.append(gevent.spawn(
            run_gevent_worker,
            pillow_name,
            num_processes=num_processes * gevent_workers + offset,
            process_number=process_number * gevent_workers + offset + worker_num,
            **options
        ))
    gevent.joinall(workers)


def run_gevent_worker(pillow_name, *, process_number, **kw):
    """Run gevent worker forever, restarting on unexpected exit"""
    while True:
        try:
            run_pillow_by_name(pillow_name, process_number=process_number, **kw)
        except Exception as exc:
            notify_exception(None, f"[{pillow_name} {process_number}] Unexpected gevent pillow exit: {exc}")


def start_pillows(pillows=None):
    """
    Actual runner for running pillow processes. Use this to run pillows.
    """
    run_pillows = pillows or get_all_pillow_instances()

    try:
        while True:
            jobs = []
            print("[pillowtop] Starting pillow processes")
            for pillow_class in run_pillows:
                p = multiprocessing.Process(target=pillow_class.run)
                p.start()
                jobs.append(p)
            print("[pillowtop] all processes started, pids: %s" % ([x.pid for x in jobs]))
            for j in jobs:
                j.join()
            print("[pillowtop] All processes complete, restarting")
    except KeyboardInterrupt:
        sys.exit()


def start_pillow(pillow_instance):
    while True:
        print("Starting pillow %s.run()" % pillow_instance.pillow_id)
        pillow_instance.run()
        print("Pillow %s.run() completed, restarting" % pillow_instance.pillow_id)
