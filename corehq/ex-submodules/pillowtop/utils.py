import json
from collections import defaultdict, namedtuple
from copy import deepcopy
from datetime import datetime
from operator import methodcaller

from django.conf import settings
from django.db import migrations

from dimagi.utils.modules import to_function
from pillowtop.dao.exceptions import (
    DocumentMismatchError,
    DocumentMissingError,
)
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.logger import pillow_logging

from corehq.apps.change_feed.connection import get_kafka_consumer
from corehq.apps.es.client import BulkActionItem
from corehq.util.django_migrations import skip_on_fresh_install


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


def get_kafka_pillow_instances():
    from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
    return [
        pillow for pillow in get_all_pillow_instances()
        if isinstance(pillow.get_change_feed(), KafkaChangeFeed)
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


class PillowConfig(namedtuple('PillowConfig', ['section', 'name', 'class_name', 'instance_generator', 'params'])):
    """
    Helper object for getting pillow classes/instances from settings
    """

    def __hash__(self):
        return hash(self.name)

    def get_class(self):
        return _import_class_or_function(self.class_name)

    def get_instance(self, **kwargs):
        if self.instance_generator:
            instance_generator_fn = _import_class_or_function(self.instance_generator)
            params = deepcopy(self.params)  # parameters defined in settings file
            params.update(kwargs)  # parameters passed in via run_ptop
            return instance_generator_fn(self.name, **params)
        else:
            return _get_pillow_instance(self.class_name)


def get_pillow_config_from_setting(section, pillow_config_string_or_dict):
    if isinstance(pillow_config_string_or_dict, str):
        return PillowConfig(
            section,
            pillow_config_string_or_dict.rsplit('.', 1)[1],
            pillow_config_string_or_dict,
            None,
            {}
        )
    else:
        assert 'class' in pillow_config_string_or_dict
        class_name = pillow_config_string_or_dict['class']
        return PillowConfig(
            section,
            pillow_config_string_or_dict.get('name', class_name),
            class_name,
            pillow_config_string_or_dict.get('instance', None),
            pillow_config_string_or_dict.get('params', {}),
        )


def get_pillow_by_name(pillow_class_name, instantiate=True, **kwargs):
    config = get_pillow_config_by_name(pillow_class_name)
    return config.get_instance(**kwargs) if instantiate else config.get_class()


def get_pillow_config_by_name(pillow_name):
    all_configs = get_all_pillow_configs()
    for config in all_configs:
        if config.name == pillow_name:
            return config
    raise PillowNotFoundError('No pillow found with name {}'.format(pillow_name))


def force_seq_int(seq):
    if seq is None or seq == '':
        return None
    elif isinstance(seq, dict):
        # multi-topic checkpoints don't support a single sequence id
        return None
    elif isinstance(seq, str):
        return int(seq.split('-')[0])
    else:
        assert isinstance(seq, int), type(seq)
        return seq


def safe_force_seq_int(seq, default=None):
    if isinstance(seq, dict):
        return default
    try:
        return force_seq_int(seq)
    except (AssertionError, ValueError):
        return default


def get_all_pillows_json(active_only=True):
    pillow_configs = get_all_pillow_configs()
    active_pillows = getattr(settings, 'ACTIVE_PILLOW_NAMES', None)
    if active_only and active_pillows:
        pillow_configs = [config for config in pillow_configs if config.name in active_pillows]

    consumer = get_kafka_consumer()
    with consumer:
        return [get_pillow_json(pillow_config, consumer) for pillow_config in pillow_configs]


def get_pillow_json(pillow_config, consumer=None):
    assert isinstance(pillow_config, PillowConfig)

    def _is_kafka(checkpoint):
        return checkpoint.sequence_format == 'json'

    pillow = pillow_config.get_instance()
    if consumer is None:
        consumer = get_kafka_consumer()

    checkpoint = pillow.get_checkpoint()
    timestamp = checkpoint.timestamp
    if timestamp:
        time_since_last = datetime.utcnow() - timestamp
        seconds_since_last = time_since_last.total_seconds()
        hours_since_last = seconds_since_last // 3600

        try:
            # remove microsecond portion
            prettified_time_since_last = str(time_since_last)
            prettified_time_since_last = prettified_time_since_last[0:prettified_time_since_last.index('.')]
        except ValueError:
            pass
    else:
        seconds_since_last = 0
        prettified_time_since_last = ''
        hours_since_last = None

    if _is_kafka(checkpoint):
        # breaking composition boundaries so that we can use one Kafka connection
        offsets = {
            "{},{}".format(tp.topic, tp.partition): offset
            for tp, offset in consumer.end_offsets(list(checkpoint.wrapped_sequence.keys())).items()
        }
    else:
        offsets = pillow.get_change_feed().get_latest_offsets_json()

    def _seq_to_int(checkpoint, seq):
        from pillowtop.models import kafka_seq_to_str
        if _is_kafka(checkpoint):
            return json.loads(kafka_seq_to_str(seq))
        else:
            return force_seq_int(seq)

    return {
        'name': pillow_config.name,
        'seq_format': checkpoint.sequence_format,
        'seq': _seq_to_int(checkpoint, checkpoint.wrapped_sequence),
        'offsets': offsets,
        'seconds_since_last': seconds_since_last,
        'time_since_last': prettified_time_since_last,
        'hours_since_last': hours_since_last
    }


ChangeError = namedtuple('ChangeError', 'change exception')


class ErrorCollector(object):
    def __init__(self):
        self.errors = []

    def add_error(self, error):
        self.errors.append(error)


def build_bulk_payload(changes, error_collector=None):
    """Process a set of changes, returning a list of BulkActionItem objects.

    :param changes: iterable of changes to process in Elasticsearch
    :param error_collector: optional ``ErrorCollector`` instance used to store
                            any any document fetch or transform exceptions
                            (exceptions raised if not provided)
    :returns: ``list`` of BulkActionItem instances
    """
    # TODO: do not transform the docs to be indexed (DocumentAdapter will
    #       perform this task in the future)
    from corehq.apps.change_feed.document_types import get_doc_meta_object_from_document

    payload = []

    def _is_deleted(change):
        doc = change.get_document()
        if doc and doc.get('doc_type'):
            return get_doc_meta_object_from_document(doc).is_deletion
        elif change.deleted:
            return bool(change.id)

    for change in changes:
        if _is_deleted(change):
            payload.append(BulkActionItem.delete_id(change.id))
        elif not change.deleted:
            try:
                doc = change.get_document()
                payload.append(BulkActionItem.index(doc))
            except Exception as e:
                if not error_collector:
                    raise
                error_collector.add_error(ChangeError(change, e))
        else:
            # See PR discussion: https://github.com/dimagi/commcare-hq/pull/31243
            #
            # Discarding changes when the deletion status is ambiguous feels
            # like guessing to me, which goes against the zen. Log a warning
            # for trackability.
            pillow_logging.warning("discarding ambiguous bulk change: %s", change)

    return payload


def ensure_matched_revisions(change, fetched_document):
    """
    This function ensures that the document fetched from a change matches the
    revision at which it was pushed to kafka at.

    See http://manage.dimagi.com/default.asp?237983 for more details

    :raises: DocumentMismatchError - Raised when the revisions of the fetched document
        and the change metadata do not match
    """

    change_has_rev = change.metadata and change.metadata.document_rev is not None
    doc_has_rev = fetched_document and '_rev' in fetched_document
    if doc_has_rev and change_has_rev:

        doc_rev = fetched_document['_rev']
        change_rev = change.metadata.document_rev
        if doc_rev != change_rev:
            fetched_rev = _convert_rev_to_int(doc_rev)
            stored_rev = _convert_rev_to_int(change_rev)
            if fetched_rev < stored_rev or stored_rev == -1:
                message = "Mismatched revs for {}: Cloudant rev {} vs. Changes feed rev {}".format(
                    change.id,
                    doc_rev,
                    change_rev
                )
                pillow_logging.warning(message)
                raise DocumentMismatchError(message)


def _convert_rev_to_int(rev):
    try:
        return int(rev.split('-')[0])
    except (ValueError, AttributeError):
        return -1


def ensure_document_exists(change):
    """
    This is to ensure that the Couch document exists in the Couch database when the
    change is processed. We only care about the scenario where the document is missing.

    :raises: DocumentMissingError - Raised when the document is missing (never existed)
    """
    change.get_document()
    if change.error_raised is not None and isinstance(change.error_raised, DocumentMissingError):
        raise change.error_raised


def bulk_fetch_changes_docs(changes, domain=None):
    """Take a set of changes and populate them with the documents if necessary.
    :returns: tuple(<changes with missing or out of date documents>, <document list>)
    """
    # break up by doctype
    changes_by_doctype = defaultdict(list)
    for change in changes:
        if domain and change.metadata.domain != domain:
            raise ValueError("Domain does not match change")
        changes_by_doctype[change.metadata.data_source_name].append(change)

    # query
    docs = []
    for _, _changes in changes_by_doctype.items():
        doc_store = _changes[0].document_store
        doc_ids_to_query = [change.id for change in _changes if change.should_fetch_document()]
        new_docs = list(doc_store.iter_documents(doc_ids_to_query))
        docs_queried_prior = [change.document for change in _changes if change.document]
        docs.extend(new_docs + docs_queried_prior)

    # catch missing docs
    bad_changes = set()
    docs_by_id = {doc['_id']: doc for doc in docs}
    for change in changes:
        if change.id not in docs_by_id:
            # we need to capture DocumentMissingError which is not possible in bulk
            #   so let pillow fall back to serial mode to capture the error for missing docs
            bad_changes.add(change)
            continue
        else:
            # set this, so that subsequent doc lookups are avoided
            change.set_document(docs_by_id[change.id])
        try:
            ensure_matched_revisions(change, docs_by_id.get(change.id))
        except DocumentMismatchError:
            bad_changes.add(change)
    return bad_changes, docs


def get_errors_with_ids(es_action_errors):
    return [
        (item['_id'], item.get('error'))
        for op_type, item in _changes_to_list(es_action_errors)
        if not (op_type == 'delete' and item.get('status') == 404)
    ]


def _changes_to_list(change_items):
    """Convert list of dict(key: value) in to a list of tuple(key, value)"""
    return list(map(methodcaller("popitem"), change_items))


def change_checkpoint_id(old_id, new_id):
    """Django migration which clones Kafka checkpoints to a new ID"""
    from pillowtop.models import KafkaCheckpoint

    @skip_on_fresh_install
    def _change_checkpoint_id(*args, **kwargs):
        for old in KafkaCheckpoint.objects.filter(checkpoint_id=old_id):
            # These may have been already created by validate_kafka_pillow_checkpoints,
            # but the offset should be 0 if they haven't been used
            new, created = KafkaCheckpoint.objects.get_or_create(
                checkpoint_id=new_id,
                topic=old.topic,
                partition=old.partition,
                defaults={"offset": 0},
            )
            if not created and new.offset != 0:
                raise Exception(
                    f"KafkaCheckpoint(checkpoint_id={new_id}, topic={old.topic}, "
                    f"partition={old.partition}) already exists and has an "
                    f"offset of {new.offset}"
                )

            new.offset = old.offset
            new.doc_modification_time = old.doc_modification_time
            new.save()

    return migrations.RunPython(
        _change_checkpoint_id,
        reverse_code=migrations.RunPython.noop,
        elidable=True,
    )
