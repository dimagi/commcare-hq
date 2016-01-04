from abc import ABCMeta, abstractmethod
from dimagi.ext import jsonobject
from pillowtop.dao.exceptions import DocumentNotFoundError


class ChangeMeta(jsonobject.JsonObject):
    """
    Metadata about a change. If available, this will be set on Change.metadata.

    This is currently only used in kafka-based pillows.
    """
    document_id = jsonobject.StringProperty(required=True)
    data_source_type = jsonobject.StringProperty(required=True)
    data_source_name = jsonobject.StringProperty(required=True)
    document_type = jsonobject.StringProperty()
    document_subtype = jsonobject.StringProperty()
    domain = jsonobject.StringProperty()
    is_deletion = jsonobject.BooleanProperty()
    _allow_dynamic_properties = False


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

    def __init__(self, id, sequence_id, document=None, deleted=False, metadata=None, document_store=None):
        self._dict = {}
        self.id = id
        self.sequence_id = sequence_id
        self.document = document
        self.deleted = deleted
        self.metadata = metadata
        self.document_store = document_store
        self._document_checked = False
        self._dict = {
            'id': self.id,
            'seq': self.sequence_id,
            'doc': self.document,
            'deleted': self.deleted,
        }

    def set_document(self, document):
        self.document = document

    def get_document(self):
        if not self.document and self.document_store and not self._document_checked:
            try:
                self.document = self.document_store.get_document(self.id)
            except DocumentNotFoundError:
                self.document = None
                self._document_checked = True  # set this flag to avoid multiple redundant lookups
        return self.document

    def __repr__(self):
        return u'Change id: {}, seq: {}, deleted: {}, metadata: {}, doc: {}'.format(
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
        raise NotImplemented('This is a read-only dictionary!')

    def __delitem__(self, key, value):
        raise NotImplemented('This is a read-only dictionary!')

    def __iter__(self):
        return iter(self._dict)

    def __contains__(self, item):
        return item in self._dict

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def pop(self, key, default):
        raise NotImplemented('This is a read-only dictionary!')

    def to_dict(self):
        return self._dict


class ChangeFeed(object):
    """
    Basic change feed API.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def iter_changes(self, since, forever):
        """
        Iterates through all changes since a certain sequence ID.
        """
        pass

    @abstractmethod
    def get_latest_change_id(self):
        """
        Should return an integer ID representing the last change - can be used
        to show progress / changes remaining to process
        """
        pass
