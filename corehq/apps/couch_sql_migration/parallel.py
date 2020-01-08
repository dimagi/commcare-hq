import logging
import os
import traceback
from contextlib import contextmanager
from threading import Event

import attr
import gevent
import gipc
from gevent.queue import Empty, Queue

from .util import ProcessError, gipc_process_error_handler

log = logging.getLogger(__name__)
RESULT_TIMEOUT = 5  # seconds


def _check_processes(obj, attrib, value):
    if value < 1:
        raise ValueError(f"one or more processes required, got {value}")


@attr.s
class Pool:
    """gevent-enabled process pool

    The first four constructor arguments are the same as those accepted
    by `multiprocessing.pool.Pool`.
    """
    processes = attr.ib(factory=os.cpu_count, validator=_check_processes)
    initializer = attr.ib(factory=lambda: _init_worker)
    initargs = attr.ib(default=())
    maxtasksperchild = attr.ib(default=None)

    def imap_unordered(self, func, iterable):
        """Process items in parallel using multiple processes

        This is similar to `multiprocessing.pool.Pool.imap_unordered()`,
        but it does not accept a `chunksize` parameter.

        This implementation yields results of successfully processed
        items and logs errors for failed items. Python's built in
        `Pool.imap_unordered()` does not gracefully handle errors;
        successfully processed items may be lost if another item causes
        an error.

        :param func: A function used to process each item. This
        function must be importable (it is pickled and passed to sub-
        processes). The return value of this function must also be
        pickleable.
        :param iterable: A sequence of items, each to be passed to
        `func`. Each item must be pickleable.
        """
        stop = Event()
        itemq = Queue(self.processes)
        resultq = Queue(self.processes * 2)
        running = list(range(self.processes))
        worker_args = self._worker_args + (func, itemq, resultq)
        workers = _thread(_worker_pool, worker_args, self.processes)
        producer = _thread(_produce_items, iterable, itemq, running, stop)
        with workers, producer:
            try:
                yield from _consume_results(resultq, running)
            finally:
                log.debug("finishing up...")
                stop.set()
                if running:
                    _discard(_consume_results(resultq, running))

    @property
    def _worker_args(self):
        return self.initializer, self.initargs, self.maxtasksperchild


def _produce_items(iterable, itemq, running, stop):
    for item in iterable:
        itemq.put(item)
        if stop.is_set() or not running:
            log.debug("stopped producing")
            break
    for x in list(running):
        itemq.put(_Stop)
    log.debug("finished producing")


def _consume_results(resultq, running):
    while running:
        try:
            result = resultq.get(timeout=RESULT_TIMEOUT)
        except Empty:
            continue
        if result is _Stop:
            log.debug("got worker stop token")
            running.pop()
        elif isinstance(result, _Error):
            log.error("error processing item in worker: %s\n%s",
                result.pid, result.value)
        else:
            yield result


def _worker_pool(worker_args, processes):
    def start_worker():
        return gevent.spawn(_process, *worker_args)

    procs = {start_worker() for x in range(processes)}
    assert processes == len(procs), (processes, procs)
    try:
        while procs:
            for proc in gevent.wait(procs, count=1):
                procs.remove(proc)
                if proc.get() == _Stop:
                    continue
                procs.add(start_worker())
                log.debug("replaced worker")
        log.debug("all workers stopped")
    finally:
        for proc in procs:
            proc.kill()


def _init_worker():
    pass


@gipc_process_error_handler()
def _worker(init, initargs, func, itemq, resultq):
    init(*initargs)
    with itemq, resultq:
        while True:
            item = itemq.get()
            if item is _Stop:
                resultq.put(_Stop)
                break
            try:
                result = func(item)
            except Exception:
                result = _Error(traceback.format_exc())
            resultq.put(result)


def _discard(results):
    # avoid deadlock on worker waiting to write to resultq
    for item in results:
        log.warn("discarding result: %r", item)


class _Stop:
    pass


@attr.s
class _Error:
    value = attr.ib()
    pid = attr.ib(factory=os.getpid, init=False)


@contextmanager
def _thread(target, *args):
    greenlet = gevent.spawn(target, *args)
    try:
        yield
    finally:
        if greenlet:
            greenlet.kill()
        greenlet.join()


def _process(init, initargs, maxtasksperchild, func, itemq, resultq):
    if maxtasksperchild is None:
        task_limit = iter(int, 1)  # no limit
    else:
        task_limit = range(maxtasksperchild)
    proc = None
    try:
        with gipc_process_error_handler(), \
                gipc.pipe() as (i_send, items), \
                gipc.pipe() as (results, r_send):
            args = (init, initargs, func, i_send, r_send)
            proc = gipc.start_process(target=_worker, args=args)
            log.debug("start worker: %s", proc.pid)
            for x in task_limit:
                items.put(itemq.get())
                result = results.get()
                resultq.put(result)
                if result is _Stop:
                    log.debug("worker stopped: %s", proc.pid)
                    return _Stop
            items.put(_Stop)
    except ProcessError:
        log.error("process error %s", proc.pid)
    finally:
        if proc is not None:
            proc.join()
