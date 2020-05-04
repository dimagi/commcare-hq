import functools
import glob
import multiprocessing
import os
import signal
import sys

from pillowtop import get_all_pillow_instances

from corehq.util.signals import SignalHandlerContext


def _do_run_pillow(pillow_class):
    try:
        print("running %s" % pillow_class)
        pillow_class.run()
    except Exception as ex:
        print("Some pillow error: %s: %s" % (pillow_class.__class__.__name__, ex))


def start_pillows(pillows=None):
    """
    Actual runner for running pillow processes. Use this to run pillows.
    """
    run_pillows = pillows or get_all_pillow_instances()

    while True:
        pids = []
        handler = functools.partial(_remove_prometheus_metric_files, pids)
        with SignalHandlerContext([signal.SIGINT, signal.SIGTERM, signal.SIGHUP], handler):
            try:
                print("[pillowtop] Starting pillow processes")
                jobs = []
                for pillow_class in run_pillows:
                    p = multiprocessing.Process(target=pillow_class.run)
                    p.start()
                    jobs.append(p)

                pids.extend(x.pid for x in jobs)
                print(f"[pillowtop] all processes started, pids: {pids}")

                for j in jobs:
                    j.join()
            finally:
                handler()

        print("[pillowtop] All processes complete, restarting")


def start_pillow(pillow_instance):
    handler = functools.partial(_remove_prometheus_metric_files, [os.getpid()])
    with SignalHandlerContext([signal.SIGINT, signal.SIGTERM, signal.SIGHUP], handler):
        try:
            while True:
                print("Starting pillow %s.run()" % pillow_instance.__class__)
                pillow_instance.run()
                print("Pillow %s.run() completed, restarting" % pillow_instance.__class__)
        finally:
            handler()


def _remove_prometheus_metric_files(pids):
    path = os.environ.get('prometheus_multiproc_dir')
    if not path:
        return

    for pid in pids:
        for file in glob.glob(os.path.join(path, '*_{}.db'.format(pid))):
            os.remove(file)
