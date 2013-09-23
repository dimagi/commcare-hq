import warnings


class PillowtopConfigurationException(Exception):
    pass


def import_settings():
    try:
        from django.conf import settings
    except Exception, ex:
        # if we are not in a django context, then import local pillowsettings
        print "django import"
        print ex
        import pillowsettings as settings
    return settings


def import_pillows(instantiate=True):
    warnings.warn('pillowtop.utils.import_pillows deprecated, '
                  'please use pillowtop.get_all_pillows instead.',
                  DeprecationWarning)
    return get_all_pillows(instantiate=instantiate)


def get_all_pillows(instantiate=True):
    settings = import_settings()

    pillowtops = []
    if hasattr(settings, 'PILLOWTOPS'):
        for full_str in settings.PILLOWTOPS:
            comps = full_str.split('.')
            pillowtop_class_str = comps[-1]
            mod_str = '.'.join(comps[0:-1])
            mod = __import__(mod_str, {}, {}, [pillowtop_class_str])
            if hasattr(mod, pillowtop_class_str):
                pillowtop_class = getattr(mod, pillowtop_class_str)
                pillowtops.append(pillowtop_class() if instantiate
                                  else pillowtop_class)
            else:
                raise PillowtopConfigurationException(
                    ("Error, the pillow class %s "
                     "could not be imported") % full_str
                )
    return pillowtops


def force_seq_int(seq):
    if seq is None:
        return None
    elif isinstance(seq, basestring):
        return int(seq.split('-')[0])
    else:
        assert isinstance(seq, int)
        return seq


def get_all_pillows_json():
    pillows = get_all_pillows()
    pillows_json = []
    for pillow in pillows:
        checkpoint = pillow.get_checkpoint()
        pillows_json.append({
            'name': pillow.__class__.__name__,
            'seq': force_seq_int(checkpoint.get('seq')),
            'old_seq': force_seq_int(checkpoint.get('old_seq')) or 0,
            'db_seq': force_seq_int(pillow.get_db_seq()),
        })
    return pillows_json
