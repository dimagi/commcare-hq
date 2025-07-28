import multiprocessing
import sys

from pillowtop import get_all_pillow_instances


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
