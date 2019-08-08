"""
Couch models for commcare cases.

For details on casexml check out:
http://bitbucket.org/javarosa/javarosa/wiki/casexml
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from collections import OrderedDict
import re
from datetime import datetime
import logging

from django.core.cache import cache
from django.conf import settings
from django.utils.translation import ugettext as _
from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case.dbaccessors import get_reverse_indices
from corehq.apps.sms.mixin import MessagingCaseContactMixin
from corehq.blobs.mixin import DeferredBlobMixin, CODES
from corehq.form_processor.abstract_models import AbstractCommCareCase, DEFAULT_PARENT_IDENTIFIER
from dimagi.ext.couchdbkit import *
from casexml.apps.case.signals import case_post_save
from casexml.apps.case import const
from dimagi.utils.modules import to_function
from dimagi.utils import web
from memoized import memoized
from dimagi.utils.indicators import ComputedDocumentMixin
from dimagi.utils.couch.undo import DELETED_SUFFIX
from couchforms.models import XFormInstance
from corehq.form_processor.exceptions import CaseNotFound
from casexml.apps.case.sharedmodels import IndexHoldingMixIn, CommCareCaseIndex, CommCareCaseAttachment
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch import (
    CouchDocLockableMixIn,
    LooselyEqualDocumentSchema,
)
import six
from six.moves import filter

INDEX_RELATIONSHIP_CHILD = 'child'
INDEX_RELATIONSHIP_EXTENSION = 'extension'


class CommCareCaseAction(LooselyEqualDocumentSchema):
    """
    An atomic action on a case. Either a create, update, or close block in
    the xml.
    """
    action_type = StringProperty(choices=list(const.CASE_ACTIONS))
    user_id = StringProperty()
    date = DateTimeProperty()
    server_date = DateTimeProperty()
    xform_id = StringProperty()
    xform_xmlns = StringProperty()
    xform_name = StringProperty()
    sync_log_id = StringProperty()

    updated_known_properties = DictProperty()
    updated_unknown_properties = DictProperty()
    indices = SchemaListProperty(CommCareCaseIndex)
    attachments = SchemaDictProperty(CommCareCaseAttachment)

    deprecated = False

    @classmethod
    def from_parsed_action(cls, date, user_id, xformdoc, action):
        if not action.action_type_slug in const.CASE_ACTIONS:
            raise ValueError("%s not a valid case action!" % action.action_type_slug)

        user_id = user_id or xformdoc.user_id
        ret = CommCareCaseAction(action_type=action.action_type_slug, date=date, user_id=user_id)

        ret.server_date = xformdoc.received_on
        ret.xform_id = xformdoc.form_id
        ret.xform_xmlns = xformdoc.xmlns
        ret.xform_name = getattr(xformdoc, 'name', '')
        ret.updated_known_properties = action.get_known_properties()

        ret.updated_unknown_properties = action.dynamic_properties
        ret.indices = [CommCareCaseIndex.from_case_index_update(i) for i in action.indices]
        ret.attachments = dict((attach_id, CommCareCaseAttachment.from_case_index_update(attach))
                               for attach_id, attach in action.attachments.items())
        if hasattr(xformdoc, "last_sync_token"):
            ret.sync_log_id = xformdoc.last_sync_token
        return ret

    @property
    def xform(self):
        try:
            return XFormInstance.get(self.xform_id) if self.xform_id else None
        except ResourceNotFound:
            logging.exception("couldn't access form {form} inside of a referenced case.".format(
                form=self.xform_id,
            ))
            return None

    @property
    def form(self):
        """For compatability with CaseTransaction"""
        return self.xform

    @property
    def form_id(self):
        """For compatability with CaseTransaction"""
        return self.xform_id

    @property
    def is_case_create(self):
        return self.action_type == const.CASE_ACTION_CREATE

    @property
    def is_case_close(self):
        return self.action_type == const.CASE_ACTION_CLOSE

    @property
    def is_case_index(self):
        return self.action_type == const.CASE_ACTION_INDEX

    @property
    def is_case_attachment(self):
        return self.action_type == const.CASE_ACTION_ATTACHMENT

    @property
    def is_case_rebuild(self):
        return self.action_type == const.CASE_ACTION_REBUILD

    def get_user_id(self):
        key = 'xform-%s-user_id' % self.xform_id
        id = cache.get(key)
        if not id:
            xform = self.xform
            try:
                id = xform.metadata.userID
            except AttributeError:
                id = None
            cache.set(key, id, 12*60*60)
        return id

    def __repr__(self):
        return "{xform}: {type} - {date} ({server_date})".format(
            xform=self.xform_id, type=self.action_type,
            date=self.date, server_date=self.server_date
        )


@six.python_2_unicode_compatible
class CommCareCase(DeferredBlobMixin, SafeSaveDocument, IndexHoldingMixIn,
                   ComputedDocumentMixin, CouchDocLockableMixIn,
                   AbstractCommCareCase, MessagingCaseContactMixin):
    """
    A case, taken from casexml.  This represents the latest
    representation of the case - the result of playing all
    the actions in sequence.
    """

    domain = StringProperty()
    export_tag = StringListProperty()
    xform_ids = StringListProperty()

    external_id = StringProperty()
    opened_on = DateTimeProperty()
    modified_on = DateTimeProperty()
    type = StringProperty()
    closed = BooleanProperty(default=False)
    closed_on = DateTimeProperty()
    user_id = StringProperty()
    owner_id = StringProperty()
    opened_by = StringProperty()
    closed_by = StringProperty()

    actions = SchemaListProperty(CommCareCaseAction)
    name = StringProperty()
    version = StringProperty()
    indices = SchemaListProperty(CommCareCaseIndex)
    case_attachments = SchemaDictProperty(CommCareCaseAttachment)

    server_modified_on = DateTimeProperty()
    _blobdb_type_code = CODES._default

    def __str__(self):
        return "CommCareCase: %s (%s)" % (self.case_id, self.get_id)

    def __setattr__(self, key, value):
        # todo: figure out whether we can get rid of this.
        # couchdbkit's auto-type detection gets us into problems for various
        # workflows here, so just force known string properties to strings
        # before setting them. this would just end up failing hard later if
        # it wasn't a string
        _STRING_ATTRS = ('external_id', 'user_id', 'owner_id', 'opened_by',
                         'closed_by', 'type', 'name')
        if key in _STRING_ATTRS:
            value = six.text_type(value or '')
        super(CommCareCase, self).__setattr__(key, value)

    def __get_case_id(self):
        return self._id

    def __set_case_id(self, id):
        self._id = id
    
    case_id = property(__get_case_id, __set_case_id)

    def set_case_id(self, case_id):
        self.__set_case_id(case_id)

    @property
    def modified_by(self):
        return self.user_id

    def __repr__(self):
        return "%s(name=%r, type=%r, id=%r)" % (
                self.__class__.__name__, self.name, self.type, self._id)

    @classmethod
    def convert_sql_relationship_id_to_couch_relationship(cls, relationship_id):
        from corehq.form_processor.models import CommCareCaseIndexSQL
        relationship = {
            CommCareCaseIndexSQL.CHILD: INDEX_RELATIONSHIP_CHILD,
            CommCareCaseIndexSQL.EXTENSION: INDEX_RELATIONSHIP_EXTENSION,
        }.get(relationship_id)

        if not relationship:
            raise ValueError("relationship_id %s not recognized" % relationship_id)

        return relationship

    @memoized
    def get_parent(self, identifier=None, relationship=None):
        indices = self.indices

        if identifier:
            indices = [index for index in indices if index.identifier == identifier]

        if relationship:
            indices = [index for index in indices if index.relationship == relationship]

        return [CommCareCase.get(index.referenced_id) for index in indices]

    @property
    def parent(self):
        """
        Returns the parent case if one exists, else None.
        NOTE: This property should only return the first parent in the list
        of indices. If for some reason your use case creates more than one,
        please write/use a different property.
        """
        result = self.get_parent(
            identifier=DEFAULT_PARENT_IDENTIFIER,
            relationship=INDEX_RELATIONSHIP_CHILD
        )
        return result[0] if result else None

    @property
    def host(self):
        result = self.get_parent(relationship=INDEX_RELATIONSHIP_EXTENSION)
        return result[0] if result else None

    @property
    def server_opened_on(self):
        try:
            open_action = self.actions[0]
            return open_action.server_date
        except Exception:
            pass

    @property
    @memoized
    def reverse_indices(self):
        return get_reverse_indices(self)

    @memoized
    def get_subcases(self, index_identifier=None):
        subcase_ids = [
            ix.referenced_id for ix in self.reverse_indices
            if (index_identifier is None or ix.identifier == index_identifier)
        ]
        return CommCareCase.view('_all_docs', keys=subcase_ids, include_docs=True)

    @property
    def is_deleted(self):
        return self.doc_type.endswith(DELETED_SUFFIX)

    @property
    def has_indices(self):
        return self.indices or self.reverse_indices

    @property
    def deletion_id(self):
        return getattr(self, '-deletion_id', None)

    @property
    def deletion_date(self):
        return getattr(self, '-deletion_date', None)

    def soft_delete(self):
        self.doc_type += DELETED_SUFFIX
        self.save()

    def to_api_json(self, lite=False):
        ret = {
            # actions excluded here
            "domain": self.domain,
            "case_id": self.case_id,
            "user_id": self.user_id,
            "closed": self.closed,
            "date_closed": self.closed_on,
            "xform_ids": self.xform_ids,
            # renamed
            "date_modified": self.modified_on,
            "version": self.version,
            # renamed
            "server_date_modified": self.server_modified_on,
            # renamed
            "server_date_opened": self.server_opened_on,
            "properties": self.get_properties_in_api_format(),
            #reorganized
            "indices": self.get_index_map(),
            "attachments": self.get_attachment_map(),
        }
        if not lite:
            ret.update({
                "reverse_indices": self.get_index_map(True),
            })
        return ret

    @classmethod
    def get(cls, id, **kwargs):
        try:
            return super(CommCareCase, cls).get(id, **kwargs)
        except ResourceNotFound:
            raise CaseNotFound(id)

    @classmethod
    def get_wrap_class(cls, data):
        try:
            settings.CASE_WRAPPER
        except AttributeError:
            cls._case_wrapper = None
        else:
            CASE_WRAPPER = to_function(settings.CASE_WRAPPER, failhard=True)
        
        if CASE_WRAPPER:
            return CASE_WRAPPER(data) or cls
        return cls

    def get_server_modified_date(self):
        # gets (or adds) the server modified timestamp
        if not self.server_modified_on:
            self.save()
        return self.server_modified_on
        
    def get_case_property(self, property):
        try:
            return getattr(self, property)
        except Exception:
            return None

    def get_closing_transactions(self):
        return [action for action in reversed(self.actions) if action.action_type == const.CASE_ACTION_CLOSE]

    def get_opening_transactions(self):
        return [action for action in self.actions if action.action_type == const.CASE_ACTION_CREATE]

    def case_properties(self):
        return self.to_json()

    def get_actions_for_form(self, xform):
        return [a for a in self.actions if a.xform_id == xform.form_id]

    def modified_since_sync(self, sync_log):
        if self.server_modified_on >= sync_log.date:
            # check all of the actions since last sync for one that had a different sync token
            return any(filter(
                lambda action: action.server_date is not None and
                               action.server_date > sync_log.date and
                               action.sync_log_id != sync_log._id,
                self.actions,
            ))
        return False

    def get_version_token(self):
        """
        A unique token for this version. 
        """
        # in theory since case ids are unique and modification dates get updated
        # upon any change, this is all we need
        return "%s::%s" % (self.case_id, self.modified_on)

    @memoized
    def get_forms(self):
        """
        Gets the form docs associated with a case. If it can't find a form
        it won't be included.
        """
        from couchforms.dbaccessors import get_forms_by_id
        return get_forms_by_id(self.xform_ids)

    def get_attachment(self, attachment_name):
        return self.fetch_attachment(attachment_name)

    def dynamic_case_properties(self):
        """(key, value) tuples sorted by key"""
        json = self.to_json()
        wrapped_case = self
        if type(self) != CommCareCase:
            wrapped_case = CommCareCase.wrap(self._doc)

        items = [
            (key, json[key])
            for key in wrapped_case.dynamic_properties()
            if re.search(r'^[a-zA-Z]', key)
        ]
        return OrderedDict(sorted(items))

    def save(self, **params):
        self.server_modified_on = datetime.utcnow()
        super(CommCareCase, self).save(**params)
        case_post_save.send(CommCareCase, case=self)


# import signals
import casexml.apps.case.signals
