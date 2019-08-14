from __future__ import absolute_import
from __future__ import unicode_literals
import base64

import datetime
import hashlib
import logging
import time
import uuid

from django.db import models

from couchdbkit import ResourceNotFound
from couchdbkit.exceptions import PreconditionFailed
from dimagi.ext.couchdbkit import (
    DocumentSchema,
    DateTimeProperty,
    StringProperty,
    DictProperty,
    SchemaListProperty,
    BooleanProperty,
    SafeSaveDocument)
from dimagi.utils.couch import CouchDocLockableMixIn
from dimagi.utils.couch.database import get_safe_read_kwargs
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.indicators import ComputedDocumentMixin
from jsonobject.base import DefaultProperty
from jsonobject.exceptions import WrappingAttributeError
from lxml import etree
from lxml.etree import XMLSyntaxError

from corehq.blobs.mixin import DeferredBlobMixin, CODES
from corehq.form_processor.abstract_models import AbstractXFormInstance
from corehq.form_processor.exceptions import XFormNotFound, MissingFormXml
from corehq.form_processor.utils import clean_metadata

from couchforms import const
from couchforms.const import ATTACHMENT_NAME
from couchforms.jsonobject_extensions import GeoPointProperty
from couchforms.signals import xform_archived, xform_unarchived
import six


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

    @property
    def commcare_version(self):
        from corehq.apps.receiverwrapper.util import get_commcare_version_from_appversion_text
        from distutils.version import LooseVersion
        version_text = get_commcare_version_from_appversion_text(self.appVersion)
        if version_text:
            return LooseVersion(version_text)


class XFormOperation(DocumentSchema):
    """
    Simple structure to represent something happening to a form.

    Currently used just by the archive workflow.
    """
    user = StringProperty()
    date = DateTimeProperty(default=datetime.datetime.utcnow)
    operation = StringProperty()  # e.g. "archived", "unarchived"


@six.python_2_unicode_compatible
class XFormInstance(DeferredBlobMixin, SafeSaveDocument,
                    ComputedDocumentMixin, CouchDocLockableMixIn,
                    AbstractXFormInstance):
    """An XForms instance."""
    domain = StringProperty()
    app_id = StringProperty()
    xmlns = StringProperty()
    form = DictProperty()
    received_on = DateTimeProperty()
    server_modified_on = DateTimeProperty()
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
    _blobdb_type_code = CODES.form_xml

    class Meta(object):
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
                try:
                    return XFormInstance.wrap(doc)
                except WrappingAttributeError:
                    raise ResourceNotFound(
                        "The doc with _id {} and doc_type {} can't be wrapped "
                        "as an XFormInstance".format(docid, doc['doc_type'])
                    )
            return db.get(docid, rev=rev, wrapper=cls.wrap, **extras)
        except ResourceNotFound:
            raise XFormNotFound(docid)

    @property
    def form_id(self):
        return self._id

    @form_id.setter
    def form_id(self, value):
        self._id = value

    @property
    def form_data(self):
        return DictProperty().unwrap(self.form)[1]

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
    def deletion_date(self):
        return getattr(self, '-deletion_date', None)

    @property
    def metadata(self):
        if const.TAG_META in self.form:
            return Metadata.wrap(clean_metadata(self.to_json()[const.TAG_FORM][const.TAG_META]))

        return None

    @property
    def time_start(self):
        # Will be addressed in https://github.com/dimagi/commcare-hq/pull/19391/
        return None

    @property
    def time_end(self):
        return None

    @property
    def commcare_version(self):
        return str(self.metadata.commcare_version)

    @property
    def app_version(self):
        return None

    def __str__(self):
        return "%s (%s)" % (self.type, self.xmlns)

    def save(self, **kwargs):
        # HACK: cloudant has a race condition when saving newly created forms
        # which throws errors here. use a try/retry loop here to get around
        # it until we find something more stable.
        RETRIES = 10
        SLEEP = 0.5  # seconds
        tries = 0
        self.server_modified_on = datetime.datetime.utcnow()
        while True:
            try:
                return super(XFormInstance, self).save(**kwargs)
            except PreconditionFailed:
                if tries == 0:
                    logging.error('doc %s got a precondition failed', self._id)
                if tries < RETRIES:
                    tries += 1
                    time.sleep(SLEEP)
                else:
                    raise

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
                raise MissingFormXml(self.form_id)

    def get_attachment(self, attachment_name):
        return self.fetch_attachment(attachment_name)

    def get_xml_element(self):
        xml_string = self.get_xml()
        if not xml_string:
            return None
        return self._xml_string_to_element(xml_string)

    def _xml_string_to_element(self, xml_string):

        def _to_xml_element(payload):
            if isinstance(payload, six.text_type):
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

    def put_attachment(self, content, name, **kw):
        if kw.get("type_code") is None:
            kw["type_code"] = (
                CODES.form_xml if name == ATTACHMENT_NAME else CODES.form_attachment
            )
        return super(XFormInstance, self).put_attachment(content, name, **kw)

    @property
    def attachments(self):
        """
        Get the extra attachments for this form. This will not include
        the form itself
        """
        def _meta_to_json(meta):
            is_image = False
            if meta.content_type is not None:
                is_image = True if meta.content_type.startswith('image/') else False

            meta_json = meta.to_json()
            meta_json['is_image'] = is_image

            return meta_json

        return {name: _meta_to_json(meta)
            for name, meta in six.iteritems(self.blobs)
            if name != ATTACHMENT_NAME}

    def xml_md5(self):
        return hashlib.md5(self.get_xml()).hexdigest()

    def archive(self, user_id=None, trigger_signals=True):
        if self.is_archived:
            return
        # If this archive was initiated by a user, delete all other stubs for this action so that this action
        # isn't overridden
        from couchforms.models import UnfinishedArchiveStub
        UnfinishedArchiveStub.objects.filter(xform_id=self.form_id).all().delete()
        from corehq.form_processor.submission_process_tracker import unfinished_archive
        with unfinished_archive(instance=self, user_id=user_id, archive=True) as archive_stub:
            self.doc_type = "XFormArchived"

            self.history.append(XFormOperation(
                user=user_id,
                operation='archive',
            ))
            self.save()
            archive_stub.archive_history_updated()
            if trigger_signals:
                xform_archived.send(sender="couchforms", xform=self)

    def unarchive(self, user_id=None, trigger_signals=True):
        if not self.is_archived:
            return
        # If this unarchive was initiated by a user, delete all other stubs for this action so that this action
        # isn't overridden
        from couchforms.models import UnfinishedArchiveStub
        UnfinishedArchiveStub.objects.filter(xform_id=self.form_id).all().delete()
        from corehq.form_processor.submission_process_tracker import unfinished_archive
        with unfinished_archive(instance=self, user_id=user_id, archive=False) as archive_stub:
            self.doc_type = "XFormInstance"
            self.history.append(XFormOperation(
                user=user_id,
                operation='unarchive',
            ))
            XFormInstance.save(self)  # subclasses explicitly set the doc type so force regular save
            archive_stub.archive_history_updated()
            if trigger_signals:
                xform_unarchived.send(sender="couchforms", xform=self)

    def publish_archive_action_to_kafka(self, user_id, archive, trigger_signals=True):
        from couchforms.models import UnfinishedArchiveStub
        from corehq.form_processor.submission_process_tracker import unfinished_archive
        # Delete the original stub
        UnfinishedArchiveStub.objects.filter(xform_id=self.form_id).all().delete()
        if trigger_signals:
            with unfinished_archive(instance=self, user_id=user_id, archive=archive):
                if archive:
                    xform_archived.send(sender="couchforms", xform=self)
                else:
                    xform_unarchived.send(sender="couchforms", xform=self)


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
            new_id = uuid.uuid4().hex
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


@six.python_2_unicode_compatible
class SubmissionErrorLog(XFormError):
    """
    When a hard submission error (typically bad XML) is received we save it
    here.
    """
    md5 = StringProperty()

    def __str__(self):
        return "Doc id: %s, Error %s" % (self.get_id, self.problem)

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
        log.deferred_put_attachment(instance, ATTACHMENT_NAME, content_type="text/xml")
        return log


class DefaultAuthContext(DocumentSchema):

    def is_valid(self):
        return True


@six.python_2_unicode_compatible
class UnfinishedSubmissionStub(models.Model):
    xform_id = models.CharField(max_length=200)
    timestamp = models.DateTimeField(db_index=True)
    saved = models.BooleanField(default=False)
    domain = models.CharField(max_length=256)
    date_queued = models.DateTimeField(null=True, db_index=True)
    attempts = models.IntegerField(default=0)

    def __str__(self):
        return six.text_type(
            "UnfinishedSubmissionStub("
            "xform_id={s.xform_id},"
            "timestamp={s.timestamp},"
            "saved={s.saved},"
            "domain={s.domain})"
        ).format(s=self)

    class Meta(object):
        app_label = 'couchforms'


@six.python_2_unicode_compatible
class UnfinishedArchiveStub(models.Model):
    xform_id = models.CharField(max_length=200)
    user_id = models.CharField(max_length=200, default=None, blank=True, null=True)
    timestamp = models.DateTimeField(db_index=True)
    archive = models.BooleanField(default=False)
    history_updated = models.BooleanField(default=False)
    domain = models.CharField(max_length=256)

    def __str__(self):
        return six.text_type(
            "UnfinishedArchiveStub("
            "xform_id={s.xform_id},"
            "user_id={s.user_id},"
            "timestamp={s.timestamp},"
            "archive={s.archive},"
            "history_updated={s.history_updated},"
            "domain={s.domain})"
        ).format(s=self)

    class Meta(object):
        app_label = 'couchforms'
