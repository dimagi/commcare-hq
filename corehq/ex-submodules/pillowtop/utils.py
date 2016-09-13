from __future__ import division
from collections import namedtuple
from datetime import datetime

import sys

import simplejson
from django.conf import settings

from dimagi.utils.chunked import chunked
from dimagi.utils.modules import to_function

from pillowtop.exceptions import PillowNotFoundError


def _get_pillow_instance(full_class_str):
    pillow_class = _import_class_or_function(full_class_str)
    if pillow_class is None:
        raise ValueError('No pillow class found for {}'.format(full_class_str))
    return pillow_class()


def _import_class_or_function(full_class_str):
    return to_function(full_class_str, failhard=settings.DEBUG)


def get_all_pillow_classes():
    return [config.get_class() for config in get_all_pillow_configs()]


def get_all_pillow_instances():
    return [config.get_instance() for config in get_all_pillow_configs()]


def get_couch_pillow_instances():
    from pillowtop.feed.couch import CouchChangeFeed
    return [
        pillow for pillow in get_all_pillow_instances()
        if isinstance(pillow.get_change_feed(), CouchChangeFeed)
    ]


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
        return _import_class_or_function(self.class_name)

    def get_instance(self):
        if self.instance_generator:
            instance_generator_fn = _import_class_or_function(self.instance_generator)
            return instance_generator_fn(self.name)
        else:
            return _get_pillow_instance(self.class_name)


def get_pillow_config_from_setting(section, pillow_config_string_or_dict):
    if isinstance(pillow_config_string_or_dict, basestring):
        return PillowConfig(
            section,
            pillow_config_string_or_dict.rsplit('.', 1)[1],
            pillow_config_string_or_dict,
            None,
        )
    else:
        assert 'class' in pillow_config_string_or_dict
        class_name = pillow_config_string_or_dict['class']
        return PillowConfig(
            section,
            pillow_config_string_or_dict.get('name', class_name),
            class_name,
            pillow_config_string_or_dict.get('instance', None),
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
    elif isinstance(seq, dict):
        # multi-topic checkpoints don't support a single sequence id
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

    pillow = pillow_config.get_instance()

    checkpoint = pillow.get_checkpoint()
    timestamp = checkpoint.timestamp
    if timestamp:
        time_since_last = datetime.utcnow() - timestamp
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
    offsets = pillow.get_change_feed().get_current_offsets()

    def _couch_seq_to_int(checkpoint, seq):
        return force_seq_int(seq) if checkpoint.sequence_format != 'json' else seq

    return {
        'name': pillow_config.name,
        'seq_format': checkpoint.sequence_format,
        'seq': _couch_seq_to_int(checkpoint, checkpoint.wrapped_sequence),
        'old_seq': _couch_seq_to_int(checkpoint, checkpoint.old_sequence) or 0,
        'offsets': offsets,
        'time_since_last': time_since_last,
        'hours_since_last': hours_since_last
    }

ChangeError = namedtuple('ChangeError', 'change exception')


class ErrorCollector(object):
    def __init__(self):
        self.errors = []

    def add_error(self, error):
        self.errors.append(error)


def build_bulk_payload(index_info, changes, doc_transform=None, error_collector=None):
    doc_transform = doc_transform or (lambda x: x)
    payload = []
    for change in changes:
        if change.deleted and change.id:
            payload.append({
                "delete": {
                    "_index": index_info.index,
                    "_type": index_info.type,
                    "_id": change.id
                }
            })
        elif not change.deleted:
            try:
                doc = change.get_document()
                doc = doc_transform(doc)
                payload.append({
                    "index": {
                        "_index": index_info.index,
                        "_type": index_info.type,
                        "_id": doc['_id']
                    }
                })
                payload.append(doc)
            except Exception as e:
                if not error_collector:
                    raise
                error_collector.add_error(ChangeError(change, e))
    return payload


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
