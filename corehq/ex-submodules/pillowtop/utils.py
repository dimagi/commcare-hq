from __future__ import division
from collections import namedtuple
from datetime import datetime
import importlib

import sys

import simplejson
from django.conf import settings

from dimagi.utils.chunked import chunked
from dimagi.utils.parsing import string_to_utc_datetime

from pillowtop.exceptions import PillowNotFoundError


def get_pillow_instance(full_class_str):
    pillow_class = get_pillow_class(full_class_str)
    return pillow_class()


def get_pillow_class(full_class_str):
    mod_path, pillow_class_name = full_class_str.rsplit('.', 1)
    try:
        mod = importlib.import_module(mod_path)
        return getattr(mod, pillow_class_name)
    except (AttributeError, ImportError):
        if settings.DEBUG:
            raise
        raise ValueError("Could not find pillowtop class '%s'" % full_class_str)


def get_all_pillow_classes():
    return [config.get_class() for config in get_all_pillow_configs()]


def get_all_pillow_instances():
    return [config.get_instance() for config in get_all_pillow_configs()]


def get_all_pillow_configs():
    return get_pillow_configs_from_settings_dict(getattr(settings, 'PILLOWTOPS', {}))


def get_pillow_configs_from_settings_dict(pillow_settings_dict):
    """
    The pillow_settings_dict is expected to be a dict mapping groups to list of pillow configs
    """
    for section, list_of_pillows in pillow_settings_dict.items():
        for pillow_config in list_of_pillows:
            yield get_pillow_config_from_setting(section, pillow_config)


class PillowConfig(namedtuple('PillowConfig', ['section', 'name', 'class_name', 'instance_generator'])):
    """
    Helper object for getting pillow classes/instances from settings
    """
    def get_class(self):
        return get_pillow_class(self.class_name)

    def get_instance(self):
        return get_pillow_instance(self.instance_generator)


def get_pillow_config_from_setting(section, pillow_config_string_or_dict):
    if isinstance(pillow_config_string_or_dict, basestring):
        return PillowConfig(
            section,
            pillow_config_string_or_dict.rsplit('.', 1)[1],
            pillow_config_string_or_dict,
            pillow_config_string_or_dict
        )
    else:
        assert 'class' in pillow_config_string_or_dict
        class_name = pillow_config_string_or_dict['class']
        return PillowConfig(
            section,
            pillow_config_string_or_dict.get('name', class_name),
            class_name,
            pillow_config_string_or_dict.get('instance', class_name),
        )


def get_pillow_by_name(pillow_class_name, instantiate=True):
    config = get_pillow_config_by_name(pillow_class_name)
    return config.get_instance() if instantiate else config.get_class()


def get_pillow_config_by_name(pillow_name):
    all_configs = get_all_pillow_configs()
    for config in all_configs:
        if config.name == pillow_name:
            return config
    raise PillowNotFoundError(u'No pillow found with name {}'.format(pillow_name))


def force_seq_int(seq):
    if seq is None or seq == '':
        return None
    elif isinstance(seq, basestring):
        return int(seq.split('-')[0])
    else:
        assert isinstance(seq, int)
        return seq


def get_all_pillows_json():
    pillow_configs = get_all_pillow_configs()
    return [get_pillow_json(pillow_config) for pillow_config in pillow_configs]


def get_pillow_json(pillow_config):
    assert isinstance(pillow_config, PillowConfig)
    from pillowtop.listener import AliasedElasticPillow

    pillow_class = pillow_config.get_class()
    pillow = (pillow_class(online=False) if issubclass(pillow_class, AliasedElasticPillow)
              else pillow_config.get_instance())

    checkpoint = pillow.get_checkpoint()
    timestamp = checkpoint.get('timestamp')
    if timestamp:
        time_since_last = datetime.utcnow() - string_to_utc_datetime(timestamp)
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
        'name': pillow_config.name,
        'seq': force_seq_int(checkpoint.get('seq')),
        'old_seq': force_seq_int(checkpoint.get('old_seq')) or 0,
        'db_seq': force_seq_int(pillow.get_change_feed().get_latest_change_id()),
        'time_since_last': time_since_last,
        'hours_since_last': hours_since_last
    }


def prepare_bulk_payloads(bulk_changes, max_size, chunk_size=100):
    payloads = ['']
    for bulk_chunk in chunked(bulk_changes, chunk_size):
        current_payload = payloads[-1]
        payload_chunk = '\n'.join(map(simplejson.dumps, bulk_chunk)) + '\n'
        appended_payload = current_payload + payload_chunk
        new_payload_size = sys.getsizeof(appended_payload)
        if new_payload_size > max_size:
            payloads.append(payload_chunk)
        else:
            payloads[-1] = appended_payload

    return filter(None, payloads)
