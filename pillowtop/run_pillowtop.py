import gevent
from socketpool.pool import ConnectionPool
from gevent import monkey; monkey.patch_all()

try:
    from django.conf import settings
except Exception, ex:
    #if we are not in a django context, then import local pillowsettings
    print ex
    import pillowsettings as settings

def import_pillows():
    pillowtops = []
    if hasattr(settings, 'PILLOWTOPS'):
        for full_str in settings.PILLOWTOPS:
            comps = full_str.split('.')
            pillowtop_class_str = comps[-1]
            mod_str = '.'.join(comps[0:-1])
            mod = __import__(mod_str, {},{},[pillowtop_class_str])
            if hasattr(mod, pillowtop_class_str):
                pillowtop_class  = getattr(mod, pillowtop_class_str)
                pillowtops.append(pillowtop_class())
    return pillowtops


#standalone pillowtop runner
import pillowsettings as pillow_settings

from restkit.conn import Connection
from gevent.pool import Pool

def start_pillows():
    pillows = import_pillows()
    pool = Pool(len(pillows)+1)
    #cpool = ConnectionPool(factory=Connection, backend='gevent')
    jobs = []
    for p in pillows:
        #p.couch_db.pool = cpool
        jobs.append(gevent.spawn(p.run))
    gevent.joinall(jobs)

if __name__ == "__main__":
    start_pillows()

