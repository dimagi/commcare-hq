from __future__ import division
import inspect
from datetime import datetime
from dateutil.parser import parse
import importlib
from django.conf import settings
import pytz


def get_pillow_instance(full_class_str):
    pillow_class = get_pillow_class(full_class_str)
    return pillow_class()


def get_pillow_class(full_class_str):
    mod_path, pillow_class_name = full_class_str.rsplit('.', 1)
    try:
        mod = importlib.import_module(mod_path)
        return getattr(mod, pillow_class_name)
    except (AttributeError, ImportError):
        if getattr(settings, 'UNIT_TESTING', False):
            raise
        raise ValueError("Could not find pillowtop class '%s'" % full_class_str)


def get_all_pillow_classes():
    return _get_all_pillows(instantiate=False)


def get_all_pillow_instances():
    return _get_all_pillows(instantiate=True)


def _get_all_pillows(instantiate=True):
    pillowtops = []
    if hasattr(settings, 'PILLOWTOPS'):
        for k, v in settings.PILLOWTOPS.items():
            for full_str in v:
                pillow_class = get_pillow_class(full_str)
                pillowtops.append(pillow_class() if instantiate else pillow_class)

    return pillowtops


def get_pillow_by_name(pillow_class_name, instantiate=True):
    if hasattr(settings, 'PILLOWTOPS'):
        for k, v in settings.PILLOWTOPS.items():
            for full_str in v:
                if pillow_class_name in full_str:
                    if instantiate:
                        return get_pillow_instance(full_str)
                    else:
                        return get_pillow_class(full_str)


def force_seq_int(seq):
    if seq is None:
        return None
    elif isinstance(seq, basestring):
        return int(seq.split('-')[0])
    else:
        assert isinstance(seq, int)
        return seq


def get_all_pillows_json():
    pillow_classes = get_all_pillow_classes()
    return [get_pillow_json(pillow_class) for pillow_class in pillow_classes]


def get_pillow_json(pillow_or_class_or_name):
    from pillowtop.listener import AliasedElasticPillow

    def instantiate(pillow_class):
        return pillow_class(online=False) if issubclass(pillow_class, AliasedElasticPillow) else pillow_class()

    if isinstance(pillow_or_class_or_name, basestring):
        pillow_class = get_pillow_by_name(pillow_or_class_or_name, instantiate=False)
        pillow = instantiate(pillow_class)
    elif inspect.isclass(pillow_or_class_or_name):
        pillow = instantiate(pillow_or_class_or_name)
    else:
        pillow = pillow_or_class_or_name

    checkpoint = pillow.get_checkpoint()
    timestamp = checkpoint.get('timestamp')
    if timestamp:
        time_since_last = datetime.now(tz=pytz.UTC) - parse(timestamp)
        hours_since_last = time_since_last.total_seconds() // 3600

        try:
            # remove microsecond portion
            time_since_last = str(time_since_last)
            time_since_last = time_since_last[0:time_since_last.index('.')]
        except ValueError:
            pass
    else:
        time_since_last = ''
        hours_since_last = None
    return {
        'name': pillow.__class__.__name__,
        'seq': force_seq_int(checkpoint.get('seq')),
        'old_seq': force_seq_int(checkpoint.get('old_seq')) or 0,
        'db_seq': force_seq_int(pillow.get_db_seq()),
        'time_since_last': time_since_last,
        'hours_since_last': hours_since_last
    }


def get_current_seq(couch_db):
    return couch_db.info()['update_seq']
