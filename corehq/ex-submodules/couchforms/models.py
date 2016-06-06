from __future__ import absolute_import
import base64

import datetime
import hashlib
import logging
import time
from jsonobject.base import DefaultProperty
from lxml import etree

from django.utils.datastructures import SortedDict
from couchdbkit.exceptions import PreconditionFailed
from dimagi.ext.couchdbkit import *
from couchdbkit import ResourceNotFound
from lxml.etree import XMLSyntaxError
from couchforms.jsonobject_extensions import GeoPointProperty
from dimagi.utils.couch import CouchDocLockableMixIn
from dimagi.utils.decorators.memoized import memoized

from dimagi.utils.indicators import ComputedDocumentMixin
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.couch.database import get_safe_read_kwargs
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.mixins import UnicodeMixIn
from corehq.blobs.mixin import DeferredBlobMixin
from corehq.util.soft_assert import soft_assert
from corehq.form_processor.abstract_models import AbstractXFormInstance
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.utils import clean_metadata

from couchforms.signals import xform_archived, xform_unarchived
from couchforms.const import ATTACHMENT_NAME
from couchforms import const


def doc_types():
    """
    Mapping of doc_type attributes in CouchDB to the class that should be instantiated.
    """
    return {
        'XFormInstance': XFormInstance,
        'XFormArchived': XFormArchived,
        'XFormDeprecated': XFormDeprecated,
        'XFormDuplicate': XFormDuplicate,
        'XFormError': XFormError,
        'SubmissionErrorLog': SubmissionErrorLog,
    }


def all_known_formlike_doc_types():
    # also pulls in extra doc types from filters/xforms.js
    return set(doc_types().keys()) | set(['XFormInstance-Deleted', 'HQSubmission'])


class Metadata(DocumentSchema):
    """
    Metadata of an xform, from a meta block structured like:

        <Meta>
            <timeStart />
            <timeEnd />
            <instanceID />
            <userID />
            <deviceID />
            <deprecatedID /> 
            <username />

            <!-- CommCare extension -->
            <appVersion />
            <location />
        </Meta>

    See spec: https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaMetaDataSchema

    username is not part of the spec but included for convenience
    """
    timeStart = DateTimeProperty()
    timeEnd = DateTimeProperty()
    instanceID = StringProperty()
    userID = StringProperty()
    deviceID = StringProperty()
    deprecatedID = StringProperty()
    username = StringProperty()
    appVersion = StringProperty()
    location = GeoPointProperty()


class XFormOperation(DocumentSchema):
    """
    Simple structure to represent something happening to a form.

    Currently used just by the archive workflow.
    """
    user = StringProperty()
    date = DateTimeProperty(default=datetime.datetime.utcnow)
    operation = StringProperty()  # e.g. "archived", "unarchived"


class XFormInstance(DeferredBlobMixin, SafeSaveDocument, UnicodeMixIn,
                    ComputedDocumentMixin, CouchDocLockableMixIn,
                    AbstractXFormInstance):
    """An XForms instance."""
    migrating_blobs_from_couch = True
    domain = StringProperty()
    app_id = StringProperty()
    xmlns = StringProperty()
    form = DictProperty()
    received_on = DateTimeProperty()
    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    partial_submission = BooleanProperty(default=False)
    history = SchemaListProperty(XFormOperation)
    auth_context = DictProperty()
    submit_ip = StringProperty()
    path = StringProperty()
    openrosa_headers = DictProperty()
    last_sync_token = StringProperty()
    # almost always a datetime, but if it's not parseable it'll be a string
    date_header = DefaultProperty()
    build_id = StringProperty()
    export_tag = DefaultProperty(name='#export_tag')

    class Meta:
        app_label = 'couchforms'

    @classmethod
    def get(cls, docid, rev=None, db=None, dynamic_properties=True):
        # copied and tweaked from the superclass's method
        if not db:
            db = cls.get_db()
        cls._allow_dynamic_properties = dynamic_properties
        # on cloudant don't get the doc back until all nodes agree
        # on the copy, to avoid race conditions
        extras = get_safe_read_kwargs()
        try:
            if cls == XFormInstance:
                doc = db.get(docid, rev=rev, **extras)
                if doc['doc_type'] in doc_types():
                    return doc_types()[doc['doc_type']].wrap(doc)
                return XFormInstance.wrap(doc)
            return db.get(docid, rev=rev, wrapper=cls.wrap, **extras)
        except ResourceNotFound:
            raise XFormNotFound
        
    @property
    def form_id(self):
        return self._id

    @form_id.setter
    def form_id(self, value):
        self._id = value

    @property
    def form_data(self):
        return self.form

    @property
    def user_id(self):
        return getattr(self.metadata, 'userID', None)

    @property
    def is_error(self):
        return self.doc_type != 'XFormInstance'

    @property
    def is_duplicate(self):
        return self.doc_type == 'XFormDuplicate'

    @property
    def is_archived(self):
        return self.doc_type == 'XFormArchived'

    @property
    def is_deprecated(self):
        return self.doc_type == 'XFormDeprecated'

    @property
    def is_submission_error_log(self):
        return self.doc_type == 'SubmissionErrorLog'

    @property
    def is_deleted(self):
        return self.doc_type.endswith(DELETED_SUFFIX)

    @property
    def is_normal(self):
        return self.doc_type == 'XFormInstance'

    @property
    def deletion_id(self):
        return getattr(self, '-deletion_id', None)

    @property
    def metadata(self):
        if const.TAG_META in self.form:
            return Metadata.wrap(clean_metadata(self.to_json()[const.TAG_FORM][const.TAG_META]))

        return None

    def __unicode__(self):
        return "%s (%s)" % (self.type, self.xmlns)

    def save(self, **kwargs):
        # HACK: cloudant has a race condition when saving newly created forms
        # which throws errors here. use a try/retry loop here to get around
        # it until we find something more stable.
        RETRIES = 10
        SLEEP = 0.5 # seconds
        tries = 0
        while True:
            try:
                return super(XFormInstance, self).save(**kwargs)
            except PreconditionFailed:
                if tries == 0:
                    logging.error('doc %s got a precondition failed' % self._id)
                if tries < RETRIES:
                    tries += 1
                    time.sleep(SLEEP)
                else:
                    raise

    def xpath(self, path):
        """
        Evaluates an xpath expression like: path/to/node and returns the value
        of that element, or None if there is no value.
        """
        _soft_assert = soft_assert(to='{}@{}'.format('brudolph', 'dimagi.com'))
        _soft_assert(False, "Reference to xpath instead of get_data")
        return safe_index(self, path.split("/"))

    def get_data(self, path):
        """
        Evaluates an xpath expression like: path/to/node and returns the value
        of that element, or None if there is no value.
        """
        return safe_index(self, path.split("/"))

    def soft_delete(self):
        self.doc_type += DELETED_SUFFIX
        self.save()

    def get_xml(self):
        try:
            return self.fetch_attachment(ATTACHMENT_NAME)
        except ResourceNotFound:
            logging.warn("no xml found for %s, trying old attachment scheme." % self.get_id)
            try:
                return self[const.TAG_XML]
            except AttributeError:
                return None

    def get_attachment(self, attachment_name):
        return self.fetch_attachment(attachment_name)

    def get_xml_element(self):
        xml_string = self.get_xml()
        if not xml_string:
            return None
        return self._xml_string_to_element(xml_string)

    def _xml_string_to_element(self, xml_string):

        def _to_xml_element(payload):
            if isinstance(payload, unicode):
                payload = payload.encode('utf-8', errors='replace')
            return etree.fromstring(payload)

        try:
            return _to_xml_element(xml_string)
        except XMLSyntaxError:
            # there is a bug at least in pact code that double
            # saves a submission in a way that the attachments get saved in a base64-encoded format
            decoded_payload = base64.b64decode(xml_string)
            element = _to_xml_element(decoded_payload)

            # in this scenario resave the attachment properly in case future calls circumvent this method
            self.save()
            self.put_attachment(decoded_payload, ATTACHMENT_NAME)
            return element

    @property
    def attachments(self):
        """
        Get the extra attachments for this form. This will not include
        the form itself
        """
        return {name: meta.to_json()
            for name, meta in self.blobs.iteritems()
            if name != ATTACHMENT_NAME}
    
    def xml_md5(self):
        return hashlib.md5(self.get_xml().encode('utf-8')).hexdigest()
    
    def archive(self, user_id=None):
        if self.is_archived:
            return
        self.doc_type = "XFormArchived"
        self.history.append(XFormOperation(
            user=user_id,
            operation='archive',
        ))
        self.save()
        xform_archived.send(sender="couchforms", xform=self)

    def unarchive(self, user_id=None):
        if not self.is_archived:
            return
        self.doc_type = "XFormInstance"
        self.history.append(XFormOperation(
            user=user_id,
            operation='unarchive',
        ))
        XFormInstance.save(self)  # subclasses explicitly set the doc type so force regular save
        xform_unarchived.send(sender="couchforms", xform=self)

    @property
    def is_archived(self):
        return self.doc_type == "XFormArchived"


class XFormError(XFormInstance):
    """
    Instances that have errors go here.
    """
    problem = StringProperty()
    orig_id = StringProperty()

    @classmethod
    def from_xform_instance(cls, instance, error_message, with_new_id=False):
        instance.__class__ = XFormError
        instance.doc_type = 'XFormError'
        instance.problem = error_message

        if with_new_id:
            new_id = XFormError.get_db().server.next_uuid()
            instance.orig_id = instance._id
            instance._id = new_id
            if '_rev' in instance:
                # clear the rev since we want to make a new doc
                del instance['_rev']

        return instance

    def save(self, *args, **kwargs):
        # we put this here, in case the doc hasn't been modified from an original 
        # XFormInstance we'll force the doc_type to change. 
        self["doc_type"] = "XFormError" 
        super(XFormError, self).save(*args, **kwargs)

    @property
    def is_error(self):
        return True

        
class XFormDuplicate(XFormError):
    """
    Duplicates of instances go here.
    """
    
    def save(self, *args, **kwargs):
        # we put this here, in case the doc hasn't been modified from an original 
        # XFormInstance we'll force the doc_type to change. 
        self["doc_type"] = "XFormDuplicate" 
        # we can't use super because XFormError also sets the doc type
        XFormInstance.save(self, *args, **kwargs)

    @property
    def is_duplicate(self):
        return True


class XFormDeprecated(XFormError):
    """
    After an edit, the old versions go here.
    """
    deprecated_date = DateTimeProperty(default=datetime.datetime.utcnow)
    orig_id = StringProperty()

    def save(self, *args, **kwargs):
        # we put this here, in case the doc hasn't been modified from an original 
        # XFormInstance we'll force the doc_type to change. 
        self["doc_type"] = "XFormDeprecated" 
        # we can't use super because XFormError also sets the doc type
        XFormInstance.save(self, *args, **kwargs)
        # should raise a signal saying that this thing got deprecated

    @property
    def is_deprecated(self):
        return True


class XFormArchived(XFormError):
    """
    Archived forms don't show up in reports
    """

    def save(self, *args, **kwargs):
        # force set the doc type and call the right superclass
        self["doc_type"] = "XFormArchived"
        XFormInstance.save(self, *args, **kwargs)

    @property
    def is_archived(self):
        return True


class SubmissionErrorLog(XFormError):
    """
    When a hard submission error (typically bad XML) is received we save it 
    here. 
    """
    md5 = StringProperty()

    def __unicode__(self):
        return u"Doc id: %s, Error %s" % (self.get_id, self.problem)

    def get_xml(self):
        return self.fetch_attachment(ATTACHMENT_NAME)
        
    def save(self, *args, **kwargs):
        # we have to override this because XFormError does too 
        self["doc_type"] = "SubmissionErrorLog" 
        # and we can't use super for the same reasons XFormError
        XFormInstance.save(self, *args, **kwargs)

    @property
    def is_submission_error_log(self):
        return True

    @classmethod
    def from_instance(cls, instance, message):
        """
        Create an instance of this record from a submission body
        """
        log = SubmissionErrorLog(
            received_on=datetime.datetime.utcnow(),
            md5=hashlib.md5(instance).hexdigest(),
            problem=message,
        )
        log.deferred_put_attachment(instance, ATTACHMENT_NAME, context_type="text/xml")
        return log


class DefaultAuthContext(DocumentSchema):

    def is_valid(self):
        return True

from django.db import models


class UnfinishedSubmissionStub(models.Model):
    xform_id = models.CharField(max_length=200)
    timestamp = models.DateTimeField()
    saved = models.BooleanField(default=False)
    domain = models.CharField(max_length=256)

    class Meta:
        app_label = 'couchforms'
