from datetime import datetime
from abc import ABCMeta, abstractmethod

from corehq.sql_db.util import handle_connection_failure, get_all_db_aliases
from jsonobject import DefaultProperty
from dimagi.ext import jsonobject
from pillowtop.dao.exceptions import DocumentNotFoundError


class ChangeMeta(jsonobject.JsonObject):
    """
    Metadata about a change. If available, this will be set on Change.metadata.

    This is only used in kafka-based pillows.
    """
    # Allow dynamic properties, so that if a new property needs to be rolled back,
    # changes pushed with that property do not create errors
    _allow_dynamic_properties = True

    document_id = DefaultProperty(required=True)

    # Only relevant for Couch documents
    document_rev = jsonobject.StringProperty()

    # 'couch' or 'sql'
    data_source_type = jsonobject.StringProperty(required=True)

    # couch database name or one of data sources listed in corehq.apps.change_feed.data_sources
    data_source_name = jsonobject.StringProperty(required=True)

    # doc_type property of doc or else the topic name
    document_type = DefaultProperty()

    document_subtype = jsonobject.StringProperty()
    domain = jsonobject.StringProperty()
    is_deletion = jsonobject.BooleanProperty()
    publish_timestamp = jsonobject.DateTimeProperty(default=datetime.utcnow)

    # track of retry attempts
    attempts = jsonobject.IntegerProperty(default=0)

    # track when first published (will not get updated on retry, unlike publish_timestamp)
    original_publication_datetime = jsonobject.DateTimeProperty(default=datetime.utcnow)

    # available to hold any associated document. For cases, this is the form ID responsible for the change
    associated_document_id = jsonobject.StringProperty()


class Change(object):
    """
    A record of a change. Provides a dict-like interface for backwards compatibility with couch changes.
    """
    PROPERTY_DICT_MAP = {
        'id': 'id',
        'sequence_id': 'seq',
        'document': 'doc',
        'deleted': 'deleted'
    }

    def __init__(self, id, sequence_id, document=None, deleted=False, metadata=None,
                 document_store=None, topic=None, partition=None):
        self._dict = {}
        self.id = id
        self.sequence_id = sequence_id
        self.topic = topic
        self.partition = partition
        self.document = document
        # on couch-based change feeds .deleted represents a hard deletion.
        # on kafka-based feeds, .deleted represents a soft deletion and is equivalent
        # to change.metadata.is_deletion.
        self.deleted = deleted
        self.metadata = metadata
        self.document_store = document_store
        self.error_raised = None
        self._document_checked = False
        self._dict = {
            'id': self.id,
            'seq': self.sequence_id,
            'doc': self.document,
            'deleted': self.deleted,
        }

    def set_document(self, document):
        # this is a public attribute, be careful when renaming
        self.document = document

    @handle_connection_failure(get_db_aliases=get_all_db_aliases)
    def get_document(self):
        if self.should_fetch_document():
            try:
                self.document = self.document_store.get_document(self.id)
            except DocumentNotFoundError as e:
                self.document = None
                self._document_checked = True  # set this flag to avoid multiple redundant lookups
                self.error_raised = e
            except Exception as err:
                raise err.__class__(
                    f'Unable to get document with ID {self.id!r} '
                    f'from document store {self.document_store!r}'
                ) from err
        return self.document

    def should_fetch_document(self):
        return not self.document and self.document_store and not self._document_checked

    def increment_attempt_count(self):
        if self.metadata:
            self.metadata.attempts += 1

    def __repr__(self):
        return 'Change id: {}, seq: {}, deleted: {}, metadata: {}, doc: {}'.format(
            self.id, self.sequence_id, self.deleted, self.metadata, self.document
        )

    def __len__(self):
        return len(self._dict)

    def __setattr__(self, name, value):
        super(Change, self).__setattr__(name, value)
        if name in self.PROPERTY_DICT_MAP:
            self._dict[self.PROPERTY_DICT_MAP[name]] = value

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        raise NotImplementedError('This is a read-only dictionary!')

    def __delitem__(self, key, value):
        raise NotImplementedError('This is a read-only dictionary!')

    def __iter__(self):
        return iter(self._dict)

    def __contains__(self, item):
        return item in self._dict

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def pop(self, key, default):
        raise NotImplementedError('This is a read-only dictionary!')

    def to_dict(self):
        return self._dict


class ChangeFeed(metaclass=ABCMeta):
    """
    Basic change feed API.
    """

    sequence_format = 'text'

    @abstractmethod
    def iter_changes(self, since, forever):
        """
        Iterates through all changes since a certain sequence ID.
        """
        pass

    @abstractmethod
    def get_latest_offsets(self):
        """
        :return: A dictionary of ``(topic/db_name, offset integer)`` pairs representing
                 the max sequence ID that is available for each topic.
        """

    def get_latest_offsets_json(self):
        """
        :return: A version of `get_latest_offsets` that returns a dictionary, but is
                 guarenteed to be valid JSON
        """
        return self.get_latest_offsets()

    @abstractmethod
    def get_processed_offsets(self):
        """
        :return: A dictionary of ``topic/dbname, offset integer`` pairs representing
                 the last sequence ID that was processed for each topic.
        """

    @abstractmethod
    def get_latest_offsets_as_checkpoint_value(self):
        """
        :return: The latest offset value in the format expected by the ``since`` param
                 of ``iter_changes``:
                   * string change ID for Cloudant and CouchDB
                   * int change ID for single kafka topic
                   * or a dict if multiple kafka topics are used
        """
