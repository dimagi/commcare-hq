from __future__ import absolute_import
from StringIO import StringIO
import base64
from functools import cmp_to_key
import re
from datetime import datetime
import logging
import copy
import sys

from django.core.cache import cache
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from couchdbkit.ext.django.schema import *
from couchdbkit.exceptions import ResourceNotFound, ResourceConflict
from PIL import Image
from casexml.apps.case.exceptions import MissingServerDate, ReconciliationError
from corehq.util.couch_helpers import CouchAttachmentsBuilder
from corehq.util.timezones.conversions import TIMEZONE_DATA_MIGRATION_COMPLETE
from couchforms.util import is_deprecation, is_override
from dimagi.utils.chunked import chunked
from dimagi.utils.django.cached_object import CachedObject, OBJECT_ORIGINAL, OBJECT_SIZE_MAP, CachedImage, IMAGE_SIZE_ORDERING
from casexml.apps.phone.xml import get_case_element
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.util import (
    get_case_xform_ids,
    reverse_indices,
)
from casexml.apps.case import const
from dimagi.utils.modules import to_function
from dimagi.utils import parsing, web
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.indicators import ComputedDocumentMixin
from couchforms.models import XFormInstance
from casexml.apps.case.sharedmodels import IndexHoldingMixIn, CommCareCaseIndex, CommCareCaseAttachment
from dimagi.utils.couch.database import SafeSaveDocument, iter_docs
from dimagi.utils.couch import (
    CouchDocLockableMixIn,
    LooselyEqualDocumentSchema,
)


"""
Couch models for commcare cases.  

For details on casexml check out:
http://bitbucket.org/javarosa/javarosa/wiki/casexml
"""

CASE_STATUS_OPEN = 'open'
CASE_STATUS_CLOSED = 'closed'
CASE_STATUS_ALL = 'all'

INDEX_ID_PARENT = 'parent'


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
        
        ret = CommCareCaseAction(action_type=action.action_type_slug, date=date, user_id=user_id)
        
        ret.server_date = xformdoc.received_on
        ret.xform_id = xformdoc.get_id
        ret.xform_xmlns = xformdoc.xmlns
        ret.xform_name = xformdoc.name
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


class CaseQueryMixin(object):
    @classmethod
    def get_by_xform_id(cls, xform_id):
        return cls.view("case/by_xform_id", reduce=False, include_docs=True,
                        key=xform_id)

    @classmethod
    def get_all_cases(cls, domain, case_type=None, owner_id=None, status=None,
                      reduce=False, include_docs=False, **kwargs):
        """
        :param domain: The domain the cases belong to.
        :param type: Restrict results to only cases of this type.
        :param owner_id: Restrict results to only cases owned by this user / group.
        :param status: Restrict results to cases with this status. Either 'open' or 'closed'.
        """
        key = cls.get_all_cases_key(domain, case_type=case_type, owner_id=owner_id, status=status)
        return CommCareCase.view('case/all_cases',
            startkey=key,
            endkey=key + [{}],
            reduce=reduce,
            include_docs=include_docs,
            **kwargs).all()

    @classmethod
    def get_all_cases_key(cls, domain, case_type=None, owner_id=None, status=None):
        """
        :param status: One of 'all', 'open' or 'closed'.
        """
        if status and status not in [CASE_STATUS_ALL, CASE_STATUS_OPEN, CASE_STATUS_CLOSED]:
            raise ValueError("Invalid value for 'status': '%s'" % status)

        key = [domain]
        prefix = status or CASE_STATUS_ALL
        if case_type:
            prefix += ' type'
            key += [case_type]
            if owner_id:
                prefix += ' owner'
                key += [owner_id]
        elif owner_id:
            prefix += ' owner'
            key += [owner_id]

        return [prefix] + key


class CommCareCase(SafeSaveDocument, IndexHoldingMixIn, ComputedDocumentMixin,
                   CaseQueryMixin, CouchDocLockableMixIn):
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

    def __unicode__(self):
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
            value = unicode(value or '')
        super(CommCareCase, self).__setattr__(key, value)

    def __get_case_id(self):
        return self._id

    def __set_case_id(self, id):
        self._id = id
    
    case_id = property(__get_case_id, __set_case_id)

    def __repr__(self):
        return "%s(name=%r, type=%r, id=%r)" % (
                self.__class__.__name__, self.name, self.type, self._id)

    @property
    @memoized
    def parent(self):
        """
        Returns the parent case if one exists, else None.
        NOTE: This property should only return the first parent in the list
        of indices. If for some reason your use case creates more than one, 
        please write/use a different property.
        """
        for index in self.indices:
            if index.identifier == INDEX_ID_PARENT:
                return CommCareCase.get(index.referenced_id)
        return None

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
        return reverse_indices(self.get_db(), self)

    @memoized
    def get_subcases(self):
        subcase_ids = [ix.referenced_id for ix in self.reverse_indices]
        return CommCareCase.view('_all_docs', keys=subcase_ids, include_docs=True)

    @property
    def has_indices(self):
        return self.indices or self.reverse_indices
        
    def to_full_dict(self):
        """
        Include calculated properties that need to be available to the case
        details display by overriding this method.

        """
        json = self.to_json()
        json['status'] = _('Closed') if self.closed else _('Open')

        return json

    def get_json(self, lite=False):
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
            "properties": dict(self.dynamic_case_properties() + {
                "external_id": self.external_id,
                "owner_id": self.owner_id,
                # renamed
                "case_name": self.name,
                # renamed
                "case_type": self.type,
                # renamed
                "date_opened": self.opened_on,
                # all custom properties go here
            }.items()),
            #reorganized
            "indices": self.get_index_map(),
            "attachments": self.get_attachment_map(),
        }
        if not lite:
            ret.update({
                "reverse_indices": self.get_index_map(True),
            })
        return ret

    @memoized
    def get_attachment_map(self):
        return dict([
            (name, {
                'url': self.get_attachment_server_url(att.attachment_key),
                'mime': att.attachment_from
            }) for name, att in self.case_attachments.items()
        ])

    @memoized
    def get_index_map(self, reversed=False):
        return dict([
            (index.identifier, {
                "case_type": index.referenced_type,
                "case_id": index.referenced_id
            }) for index in (self.indices if not reversed else self.reverse_indices)
        ])

    @classmethod
    def get(cls, id, strip_history=False, **kwargs):
        if strip_history:
            return cls.get_lite(id)
        return super(CommCareCase, cls).get(id, **kwargs)

    @classmethod
    def get_with_rebuild(cls, id):
        try:
            return cls.get(id)
        except ResourceNotFound:
            from casexml.apps.case.cleanup import rebuild_case
            case = rebuild_case(id)
            if case is None:
                raise
            return case

    @classmethod
    def get_lite(cls, id, wrap=True):
        results = cls.get_db().view("case/get_lite", key=id, include_docs=False).one()
        if results is None:
            raise ResourceNotFound('no case with id %s exists' % id)
        if wrap:
            return cls.wrap(results['value'])
        else:
            return results['value']

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

    @classmethod
    def bulk_get_lite(cls, ids, wrap=True, chunksize=100):
        wrapper = lambda doc: cls.get_wrap_class(doc).wrap(doc) if wrap else doc
        for ids in chunked(ids, chunksize):
            for row in cls.get_db().view("case/get_lite", keys=ids, include_docs=False):
                yield wrapper(row['value'])

    def get_preloader_dict(self):
        """
        Gets the case as a dictionary for use in touchforms preloader framework
        """
        ret = copy.copy(self._doc)
        ret["case-id"] = self.get_id
        return ret

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

    def set_case_property(self, property, value):
        setattr(self, property, value)

    def case_properties(self):
        return self.to_json()

    def get_actions_for_form(self, form_id):
        return [a for a in self.actions if a.xform_id == form_id]
        
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
        forms = iter_docs(self.get_db(), self.xform_ids)
        return [XFormInstance(form) for form in forms]

    def get_attachment(self, attachment_key):
        return self.fetch_attachment(attachment_key)

    def get_attachment_server_url(self, attachment_key):
        """
        A server specific URL for remote clients to access case attachment resources async.
        """
        if attachment_key in self.case_attachments:
            return "%s%s" % (web.get_url_base(),
                             reverse("api_case_attachment", kwargs={
                                 "domain": self.domain,
                                 "case_id": self._id,
                                 "attachment_id": attachment_key,
                             })
            )
        else:
            return None


    @classmethod
    def cache_and_get_object(cls, cobject, case_id, attachment_key, size_key=OBJECT_ORIGINAL):
        """
        Retrieve cached_object or image and cache sizes if necessary
        """
        if not cobject.is_cached():
            resp = cls.get_db().fetch_attachment(case_id, attachment_key, stream=True)
            stream = StringIO(resp.read())
            headers = resp.resp.headers
            cobject.cache_put(stream, headers)

        meta, stream = cobject.get(size_key=size_key)
        return meta, stream


    @classmethod
    def fetch_case_image(cls, case_id, attachment_key, filesize_limit=0, width_limit=0, height_limit=0, fixed_size=None):
        """
        Return (metadata, stream) information of best matching image attachment.
        attachment_key is the case property of the attachment
        attachment filename is the filename of the original submission - full extension and all.
        """
        if fixed_size is not None:
            size_key = fixed_size
        else:
            size_key = OBJECT_ORIGINAL

        constraint_dict = {}
        if filesize_limit:
            constraint_dict['content_length'] = filesize_limit

        if height_limit:
            constraint_dict['height'] = height_limit

        if width_limit:
            constraint_dict['width'] = width_limit
        do_constrain = bool(constraint_dict)

        # if size key is None, then one of the limit criteria are set
        attachment_cache_key = "%(case_id)s_%(attachment)s" % {
            "case_id": case_id,
            "attachment": attachment_key,
        }

        cached_image = CachedImage(attachment_cache_key)
        meta, stream = cls.cache_and_get_object(cached_image, case_id, attachment_key, size_key=size_key)

        # now that we got it cached, let's check for size constraints

        if do_constrain:
            #check this size first
            #see if the current size matches the criteria

            def meets_constraint(constraints, meta):
                for c, limit in constraints.items():
                    if meta[c] > limit:
                        return False
                return True

            if meets_constraint(constraint_dict, meta):
                #yay, do nothing
                pass
            else:
                #this meta is no good, find another one
                lesser_keys = IMAGE_SIZE_ORDERING[0:IMAGE_SIZE_ORDERING.index(size_key)]
                lesser_keys.reverse()
                is_met = False
                for lesser_size in lesser_keys:
                    less_meta, less_stream = cached_image.get_size(lesser_size)
                    if meets_constraint(constraint_dict, less_meta):
                        meta = less_meta
                        stream = less_stream
                        is_met = True
                        break
                if not is_met:
                    meta = None
                    stream = None

        return meta, stream


    @classmethod
    def fetch_case_attachment(cls, case_id, attachment_key, fixed_size=None, **kwargs):
        """
        Return (metadata, stream) information of best matching image attachment.
        TODO: This should be the primary case_attachment retrieval method, the image one is a silly separation of similar functionality
        Additional functionality to be abstracted by content_type of underlying attachment
        """
        size_key = OBJECT_ORIGINAL
        if fixed_size is not None and fixed_size in OBJECT_SIZE_MAP:
            size_key = fixed_size

        # if size key is None, then one of the limit criteria are set
        attachment_cache_key = "%(case_id)s_%(attachment)s" % {
            "case_id": case_id,
            "attachment": attachment_key
        }

        cobject = CachedObject(attachment_cache_key)
        meta, stream = cls.cache_and_get_object(cobject, case_id, attachment_key, size_key=size_key)

        return meta, stream

    @classmethod
    def from_case_update(cls, case_update, xformdoc):
        """
        Create a case object from a case update object.
        """
        assert not is_deprecation(xformdoc)  # you should never be able to create a case from a deleted update
        case = cls()
        case._id = case_update.id
        case.modified_on = parsing.string_to_datetime(case_update.modified_on_str) \
                            if case_update.modified_on_str else datetime.utcnow()
        
        # apply initial updates, if present
        case.update_from_case_update(case_update, xformdoc)
        return case
    
    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        if case_update.has_referrals():
            logging.error('Form {} touching case {} in domain {} is still using referrals'.format(
                xformdoc._id, case_update.id, getattr(xformdoc, 'domain', None))
            )
            raise Exception(_('Sorry, referrals are no longer supported!'))

        if is_deprecation(xformdoc):
            # Mark all of the form actions as deprecated. These will get removed on rebuild.
            # This assumes that there is a second update coming that will actually
            # reapply the equivalent actions from the form that caused the current
            # one to be deprecated (which is what happens in form processing).
            for a in self.actions:
                if a.xform_id == xformdoc.orig_id:
                    a.deprecated = True

            # short circuit the rest of this since we don't actually want to
            # do any case processing
            return
        elif is_override(xformdoc):
            # This form is overriding a deprecated form.
            # Apply the actions just after the last action with this form type.
            # This puts the overriding actions in the right order relative to the others.
            prior_actions = [a for a in self.actions if a.xform_id == xformdoc._id]
            if prior_actions:
                action_insert_pos = self.actions.index(prior_actions[-1]) + 1
                # slice insertion
                # http://stackoverflow.com/questions/7376019/python-list-extend-to-index/7376026#7376026
                self.actions[action_insert_pos:action_insert_pos] = case_update.get_case_actions(xformdoc)
            else:
                self.actions.extend(case_update.get_case_actions(xformdoc))
        else:
            # normal form - just get actions and apply them on the end
            self.actions.extend(case_update.get_case_actions(xformdoc))

        # rebuild the case
        local_forms = {xformdoc._id: xformdoc}
        local_forms.update(other_forms or {})
        self.rebuild(strict=False, xforms=local_forms)

        if case_update.version:
            self.version = case_update.version

    def _apply_action(self, action, xform):
        if action.action_type == const.CASE_ACTION_CREATE:
            self.apply_create(action)
        elif action.action_type == const.CASE_ACTION_UPDATE:
            self.apply_updates(action)
        elif action.action_type == const.CASE_ACTION_INDEX:
            self.update_indices(action.indices)
        elif action.action_type == const.CASE_ACTION_CLOSE:
            self.apply_close(action)
        elif action.action_type == const.CASE_ACTION_ATTACHMENT:
            self.apply_attachments(action, xform)
        elif action.action_type == const.CASE_ACTION_COMMTRACK:
            pass  # no action needed here, it's just a placeholder stub
        elif action.action_type == const.CASE_ACTION_REBUILD:
            pass
        else:
            raise ValueError("Can't apply action of type %s: %s" % (
                action.action_type,
                self.get_id,
            ))

        # override any explicit properties from the update
        if action.user_id:
            self.user_id = action.user_id
        if self.modified_on is None or action.date > self.modified_on:
            self.modified_on = action.date

    def apply_create(self, create_action):
        """
        Applies a create block to a case.

        Note that all unexpected attributes are ignored (thrown away)
        """
        for k, v in create_action.updated_known_properties.items():
            setattr(self, k, v)

        if not self.opened_on:
            self.opened_on = create_action.date
        if not self.opened_by:
            self.opened_by = create_action.user_id

    def apply_updates(self, update_action):
        """
        Applies updates to a case
        """
        for k, v in update_action.updated_known_properties.items():
            setattr(self, k, v)

        properties = self.properties()
        for item in update_action.updated_unknown_properties:
            if item not in const.CASE_TAGS:
                value = update_action.updated_unknown_properties[item]
                if isinstance(properties.get(item), StringProperty):
                    value = unicode(value)
                self[item] = value

    def apply_attachments(self, attachment_action, xform=None):
        """

        if xform is provided, attachments will be looked for
        in the xform's _attachments.
        They should be base64 encoded under _attachments[name]['data']

        """
        # the actions and _attachment must be added before the first saves can happen
        # todo attach cached attachment info
        def fetch_attachment(name):
            if xform and 'data' in xform._attachments[name]:
                assert xform._id == attachment_action.xform_id
                return base64.b64decode(xform._attachments[name]['data'])
            else:
                return XFormInstance.get_db().fetch_attachment(attachment_action.xform_id, name)

        stream_dict = {}
        # cache all attachment streams from xform
        for k, v in attachment_action.attachments.items():
            if v.is_present:
                # fetch attachment, update metadata, get the stream
                attach_data = fetch_attachment(v.attachment_src)
                stream_dict[k] = attach_data
                v.attachment_size = len(attach_data)

                if v.is_image:
                    img = Image.open(StringIO(attach_data))
                    img_size = img.size
                    props = dict(width=img_size[0], height=img_size[1])
                    v.attachment_properties = props

        update_attachments = {}
        for k, v in self.case_attachments.items():
            if v.is_present:
                update_attachments[k] = v

        if self._attachments:
            attachment_builder = CouchAttachmentsBuilder(
                self['_attachments'])
        else:
            attachment_builder = CouchAttachmentsBuilder()

        for k, v in attachment_action.attachments.items():
            # grab xform_attachments
            # copy over attachments from form onto case
            update_attachments[k] = v
            if v.is_present:
                #fetch attachment from xform
                attachment_key = v.attachment_key
                attach = stream_dict[attachment_key]
                attachment_builder.add(name=k, content=attach,
                                       content_type=v.server_mime)
            else:
                try:
                    attachment_builder.remove(k)
                except KeyError:
                    pass
                del update_attachments[k]
        self._attachments = attachment_builder.to_json()
        self.case_attachments = update_attachments

    def apply_close(self, close_action):
        self.closed = True
        self.closed_on = close_action.date
        self.closed_by = close_action.user_id

    def check_action_order(self):
        action_dates = [a.server_date for a in self.actions if a.server_date]
        return action_dates == sorted(action_dates)

    def reconcile_actions(self, rebuild=False, xforms=None):
        """
        Runs through the action list and tries to reconcile things that seem
        off (for example, out-of-order submissions, duplicate actions, etc.).

        This method raises a ReconciliationError if anything goes wrong.
        """
        def _check_preconditions():
            error = None
            for a in self.actions:
                if a.server_date is None:
                    error = u"Case {0} action server_date is None: {1}"
                elif a.xform_id is None:
                    error = u"Case {0} action xform_id is None: {1}"
                if error:
                    raise ReconciliationError(error.format(self.get_id, a))

        _check_preconditions()

        # this would normally work except we only recently started using the
        # form timestamp as the modification date so we have to do something
        # fancier to deal with old data
        deduplicated_actions = list(set(self.actions))

        def _further_deduplicate(action_list):
            def actions_match(a1, a2):
                # if everything but the server_date match, the actions match.
                # this will allow for multiple case blocks to be submitted
                # against the same case in the same form so long as they
                # are different
                a1doc = copy.copy(a1._doc)
                a2doc = copy.copy(a2._doc)
                a2doc['server_date'] = a1doc['server_date']
                a2doc['date'] = a1doc['date']
                return a1doc == a2doc

            ret = []
            for a in action_list:
                found_actions = [other for other in ret if actions_match(a, other)]
                if found_actions:
                    if len(found_actions) != 1:
                        error = (u"Case {0} action conflicts "
                                 u"with multiple other actions: {1}")
                        raise ReconciliationError(error.format(self.get_id, a))
                    match = found_actions[0]
                    # when they disagree, choose the _earlier_ one as this is
                    # the one that is likely timestamped with the form's date
                    # (and therefore being processed later in absolute time)
                    ret[ret.index(match)] = a if a.server_date < match.server_date else match
                else:
                    ret.append(a)
            return ret

        deduplicated_actions = _further_deduplicate(deduplicated_actions)
        sorted_actions = sorted(
            deduplicated_actions,
            key=_action_sort_key_function(self)
        )
        if sorted_actions:
            if sorted_actions[0].action_type != const.CASE_ACTION_CREATE:
                error = u"Case {0} first action not create action: {1}"
                raise ReconciliationError(
                    error.format(self.get_id, sorted_actions[0])
                )
        self.actions = sorted_actions
        if rebuild:
            # it's pretty important not to block new case changes
            # just because previous case changes have been bad
            self.rebuild(strict=False, xforms=xforms)

    def rebuild(self, strict=True, xforms=None):
        """
        Rebuilds the case state in place from its actions.

        If strict is True, this will enforce that the first action must be a create.
        """
        from casexml.apps.case.cleanup import reset_state

        xforms = xforms or {}
        reset_state(self)
        # try to re-sort actions if necessary
        try:
            self.actions = sorted(self.actions, key=_action_sort_key_function(self))
        except MissingServerDate:
            # only worry date reconciliation if in strict mode
            if strict:
                raise

        # remove all deprecated actions during rebuild.
        self.actions = [a for a in self.actions if not a.deprecated]
        actions = copy.deepcopy(list(self.actions))

        if strict:
            if actions[0].action_type != const.CASE_ACTION_CREATE:
                error = u"Case {0} first action not create action: {1}"
                raise ReconciliationError(
                    error.format(self.get_id, self.actions[0])
                )

        for a in actions:
            self._apply_action(a, xforms.get(a.xform_id))

        self.xform_ids = []
        for a in self.actions:
            if a.xform_id and a.xform_id not in self.xform_ids:
                self.xform_ids.append(a.xform_id)

    def dynamic_case_properties(self):
        """(key, value) tuples sorted by key"""
        json = self.to_json()
        wrapped_case = self
        if type(self) != CommCareCase:
            wrapped_case = CommCareCase.wrap(self._doc)

        return sorted([(key, json[key]) for key in wrapped_case.dynamic_properties()
                       if re.search(r'^[a-zA-Z]', key)])

    def save(self, **params):
        self.server_modified_on = datetime.utcnow()
        super(CommCareCase, self).save(**params)
        case_post_save.send(CommCareCase, case=self)

    def force_save(self, **params):
        try:
            self.save()
        except ResourceConflict:
            conflict = CommCareCase.get(self._id)
            # if there's a conflict, make sure we know about every
            # form in the conflicting doc
            missing_forms = set(conflict.xform_ids) - set(self.xform_ids)
            if missing_forms:
                logging.exception('doc update conflict saving case {id}. missing forms: {forms}'.format(
                    id=self._id,
                    forms=",".join(missing_forms)
                ))
                raise
            # couchdbkit doesn't like to let you set _rev very easily
            self._doc["_rev"] = conflict._rev
            self.force_save()

    def to_xml(self, version):
        from xml.etree import ElementTree
        if self.closed:
            elem = get_case_element(self, ('close'), version)
        else:
            elem = get_case_element(self, ('create', 'update'), version)
        return ElementTree.tostring(elem)
    
    def get_xform_ids_from_couch(self):
        """
        Like xform_ids, but will grab the raw output from couch (including
        potential duplicates or other forms, so that they can be reprocessed
        if desired).
        """
        return get_case_xform_ids(self._id)

    # The following methods involving display configuration should probably go
    # in their own layer, but for now it seems fine.
    @classmethod
    def get_display_config(cls):
        return [
            {
                "layout": [
                    [
                        {
                            "expr": "name",
                            "name": _("Name"),
                        },
                        {
                            "expr": "opened_on",
                            "name": _("Opened On"),
                            "parse_date": True,
                            "is_utc": TIMEZONE_DATA_MIGRATION_COMPLETE,
                        },
                        {
                            "expr": "modified_on",
                            "name": _("Modified On"),
                            "parse_date": True,
                            "is_utc": TIMEZONE_DATA_MIGRATION_COMPLETE,
                        },
                        {
                            "expr": "closed_on",
                            "name": _("Closed On"),
                            "parse_date": True,
                            "is_utc": TIMEZONE_DATA_MIGRATION_COMPLETE,
                        },
                    ],
                    [
                        {
                            "expr": "type",
                            "name": _("Case Type"),
                            "format": '<code>{0}</code>',
                        },
                        {
                            "expr": "user_id",
                            "name": _("Last Submitter"),
                            "process": 'doc_info',
                        },
                        {
                            "expr": "owner_id",
                            "name": _("Owner"),
                            "process": 'doc_info',
                        },
                        {
                            "expr": "_id",
                            "name": _("Case ID"),
                        },
                    ],
                ],
            }
        ]

    @property
    def related_cases_columns(self):
        return [
            {
                'name': _('Status'),
                'expr': "status"
            },
            {
                'name': _('Date Opened'),
                'expr': "opened_on",
                'parse_date': True,
                "is_utc": TIMEZONE_DATA_MIGRATION_COMPLETE,
            },
            {
                'name': _('Date Modified'),
                'expr': "modified_on",
                'parse_date': True,
                "is_utc": TIMEZONE_DATA_MIGRATION_COMPLETE,
            }
        ]

    @property
    def related_type_info(self):
        return None


import casexml.apps.case.signals


class CommCareCaseGroup(Document):
    """
        This is a group of CommCareCases. Useful for managing cases in larger projects.
    """
    name = StringProperty()
    domain = StringProperty()
    cases = ListProperty()
    timezone = StringProperty()

    def get_time_zone(self):
        # Necessary for the CommCareCaseGroup to interact with CommConnect, as if using the CommCareMobileContactMixin
        # However, the entire mixin is not necessary.
        return self.timezone

    def get_cases(self, limit=None, skip=None):
        case_ids = self.cases
        if skip is not None:
            case_ids = case_ids[skip:]
        if limit is not None:
            case_ids = case_ids[:limit]
        for case_doc in iter_docs(CommCareCase.get_db(), case_ids):
            # don't let CommCareCase-Deleted get through
            if case_doc['doc_type'] == 'CommCareCase':
                yield CommCareCase.wrap(case_doc)

    def get_total_cases(self, clean_list=False):
        if clean_list:
            self.clean_cases()
        return len(self.cases)

    def clean_cases(self):
        cleaned_list = []
        for case_doc in iter_docs(CommCareCase.get_db(), self.cases):
            # don't let CommCareCase-Deleted get through
            if case_doc['doc_type'] == 'CommCareCase':
                cleaned_list.append(case_doc['_id'])
        if len(self.cases) != len(cleaned_list):
            self.cases = cleaned_list
            self.save()

    @classmethod
    def get_by_domain(cls, domain, limit=None, skip=None, include_docs=True):
        extra_kwargs = {}
        if limit is not None:
            extra_kwargs['limit'] = limit
        if skip is not None:
            extra_kwargs['skip'] = skip
        return cls.view(
            'case/groups_by_domain',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=include_docs,
            reduce=False,
            **extra_kwargs
        ).all()

    @classmethod
    def get_total(cls, domain):
        data = cls.get_db().view(
            'case/groups_by_domain',
            startkey=[domain],
            endkey=[domain, {}],
            reduce=True
        ).first()
        return data['value'] if data else 0


def _action_sort_key_function(case):
    def _action_cmp(first_action, second_action):
        # if the forms aren't submitted by the same user, just default to server dates
        if first_action.user_id != second_action.user_id:
            return cmp(first_action.server_date, second_action.server_date)
        else:
            form_ids = list(case.xform_ids)

            def _sortkey(action):
                if not action.server_date or not action.date:
                    raise MissingServerDate()

                form_cmp = lambda form_id: (form_ids.index(form_id)
                                            if form_id in form_ids else sys.maxint, form_id)
                # if the user is the same you should compare with the special logic below
                # if the user is not the same you should compare just using received_on
                return (
                    # this is sneaky - it's designed to use just the date for the
                    # server time in case the phone submits two forms quickly out of order
                    action.server_date.date(),
                    action.date,
                    form_cmp(action.xform_id),
                    _type_sort(action.action_type),
                )

            return cmp(_sortkey(first_action), _sortkey(second_action))

    return cmp_to_key(_action_cmp)


def _type_sort(action_type):
    """
    Consistent ordering for action types
    """
    return const.CASE_ACTIONS.index(action_type)
