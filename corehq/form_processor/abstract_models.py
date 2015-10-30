from abc import abstractmethod, abstractproperty, ABCMeta
from dimagi.ext.jsonobject import (
    JsonObject,
    StringProperty,
    DictProperty,
    BooleanProperty,
    DateTimeProperty,
    ListProperty,
    IntegerProperty,
)
from jsonobject.base import DefaultProperty


class AbstractXFormInstance():
    accessable_properties = [
        'domain',
        'app_id',
        'xmlns',
        'received_on',
        'partial_submission',
        'submit_ip',
        'path',
        'last_sync_token',
        'build_id',
    ]

    @abstractproperty
    def id(self):
        raise NotImplementedError()

    @abstractproperty
    def auth_context(self):
        raise NotImplementedError()

    @abstractproperty
    def doc_type(self):
        raise NotImplementedError()

    @abstractproperty
    def form(self):
        raise NotImplementedError()

    @abstractmethod
    def get_data(self, xpath):
        raise NotImplementedError()

    @abstractmethod
    def get_attachment(self, attachment_name):
        raise NotImplementedError()

    @abstractmethod
    def archive(self, xform_generic, user=None):
        raise NotImplementedError()

    @abstractmethod
    def unarchive(self, xform_generic, user=None):
        raise NotImplementedError()

    @abstractmethod
    def get_xml_element(self):
        raise NotImplementedError()

    @abstractmethod
    def get(self, xform_id):
        raise NotImplementedError()

    @abstractmethod
    def save(self, *args, **kwargs):
        raise NotImplementedError()

    @abstractmethod
    def set_submission_properties(self, submission_post):
        raise NotImplementedError()


class AbstractCommCareCase(object):

    @abstractproperty
    def id(self):
        raise NotImplementedError()

    @abstractmethod
    def hard_delete(self):
        raise NotImplementedError()

    @abstractmethod
    def soft_delete(self):
        raise NotImplementedError()

    @abstractmethod
    def get_attachment(self, attachment_name):
        raise NotImplementedError()

    @abstractproperty
    def is_deleted(self):
        raise NotImplementedError()

    @classmethod
    def get_cases(cls, ids):
        raise NotImplementedError()

    @classmethod
    def get_case_xform_ids(cls, case_id):
        raise NotImplementedError()
