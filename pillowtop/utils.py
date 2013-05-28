class PillowtopConfigurationException(Exception):
    pass


def import_settings():
    try:
        from django.conf import settings
    except Exception, ex:
        #if we are not in a django context, then import local pillowsettings
        print "django import"
        print ex
        import pillowsettings as settings
    return settings


def import_pillows(instantiate=True):
    settings = import_settings()

    pillowtops = []
    if hasattr(settings, 'PILLOWTOPS'):
        for full_str in settings.PILLOWTOPS:
            comps = full_str.split('.')
            pillowtop_class_str = comps[-1]
            mod_str = '.'.join(comps[0:-1])
            mod = __import__(mod_str, {},{},[pillowtop_class_str])
            if hasattr(mod, pillowtop_class_str):
                pillowtop_class  = getattr(mod, pillowtop_class_str)
                pillowtops.append(pillowtop_class() if instantiate else pillowtop_class)
            else:
                raise PillowtopConfigurationException("Error, the pillow class %s could not be imported" % full_str)
    return pillowtops