from gevent import monkey; monkey.patch_all()
from gevent.pool import Pool
from restkit.session import set_session; set_session("gevent")
from pillowtop.utils import import_pillows


#standalone pillowtop runner
def start_pillows():
    #gevent patching: logging doesn't seem to work unless thread is not patched

    pillows = import_pillows()
    pool = Pool(len(pillows))
    while True:
        for p in pillows:
            pool.spawn(p.run)
        pool.join()
        print "Pillows all joined and completed - restarting again"
        #this shouldn't happen

if __name__ == "__main__":
    start_pillows()

