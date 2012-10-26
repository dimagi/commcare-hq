import gevent
from gevent.pool import Pool

def import_pillows():
    try:
        from django.conf import settings
    except Exception, ex:
        #if we are not in a django context, then import local pillowsettings
        print "django import"
        print ex
        import pillowsettings as settings

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
def start_pillows():
    #gevent patching: logging doesn't seem to work unless thread is not patched
    from gevent import monkey; monkey.patch_all(thread=False)
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

