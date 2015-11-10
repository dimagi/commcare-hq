import os
import collections
import hashlib

from lxml import etree
from json_field.fields import JSONField
from django.conf import settings
from django.db import models, transaction

from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.decorators.memoized import memoized
from dimagi.ext import jsonobject
from couchforms.signals import xform_archived, xform_unarchived
from couchforms import const
from couchforms.jsonobject_extensions import GeoPointProperty

from .abstract_models import AbstractXFormInstance, AbstractCommCareCase
from .exceptions import XFormNotFound


Attachment = collections.namedtuple('Attachment', 'name content content_type')


class PreSaveHashableMixin(object):
    hash_property = None

    def __hash__(self):
        hash_val = getattr(self, self.hash_property, None)
        if not hash_val:
            raise TypeError("Form instances without form ID value are unhashable")
        return hash(hash_val)


class SaveStateMixin(object):
    def is_saved(self):
        return bool(self._get_pk_val())


class AttachmentMixin(SaveStateMixin):
    """Requires the model to be linked to the attachments model via the 'attachments' related name.
    """
    ATTACHMENTS_RELATED_NAME = 'attachments'

    def get_attachment(self, attachment_name):
        return self.get_attachment_meta(attachment_name).read_content()

    def get_attachment_meta(self, attachment_name):
        if hasattr(self, 'unsaved_attachments'):
            for attachment in self.unsaved_attachments:
                if attachment.name == attachment_name:
                    return attachment
        elif self.is_saved():
            return self.attachments.filter(name=attachment_name).first()


class XFormInstanceSQL(PreSaveHashableMixin, models.Model, RedisLockableMixIn, AttachmentMixin, AbstractXFormInstance):
    """An XForms SQL instance."""
    NORMAL = 0
    ARCHIVED = 1
    DEPRECATED = 2
    DUPLICATE = 3
    ERROR = 4
    SUBMISSION_ERROR_LOG = 5
    STATES = (
        (NORMAL, 'normal'),
        (ARCHIVED, 'archived'),
        (DEPRECATED, 'deprecated'),
        (DUPLICATE, 'duplicate'),
        (ERROR, 'error'),
        (SUBMISSION_ERROR_LOG, 'submission_error'),
    )

    hash_property = 'form_uuid'

    form_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255, null=True)

    # When a form is deprecated, the existing form receives a new id and its original id is stored in orig_id
    orig_id = models.CharField(max_length=255, null=True)

    # When a form is deprecated, the new form gets a reference to the deprecated form
    deprecated_form_id = models.CharField(max_length=255, null=True)

    # Stores the datetime of when a form was deprecated
    edited_on = models.DateTimeField(null=True)

    # The time at which the server has received the form
    received_on = models.DateTimeField()

    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    auth_context = JSONField(lazy=True)
    openrosa_headers = JSONField(lazy=True)
    partial_submission = models.BooleanField(default=False)
    submit_ip = models.CharField(max_length=255, null=True)
    last_sync_token = models.CharField(max_length=255, null=True)
    problem = models.TextField(null=True)
    # almost always a datetime, but if it's not parseable it'll be a string
    date_header = models.DateTimeField(null=True)
    build_id = models.CharField(max_length=255, null=True)
    # export_tag = DefaultProperty(name='#export_tag')
    state = models.PositiveSmallIntegerField(choices=STATES, default=NORMAL)

    def __get_form_id(self):
        return self.form_uuid

    def __set_form_id(self, _id):
        self.form_uuid = _id

    form_id = property(__get_form_id, __set_form_id)

    @classmethod
    def get(cls, xform_id):
        try:
            return XFormInstanceSQL.objects.get(form_uuid=xform_id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound

    @classmethod
    def get_with_attachments(cls, xform_id):
        # NOOP for the SQL XFormInstance
        return cls.get(xform_id)

    @classmethod
    def get_obj_id(cls, obj):
        return obj.form_uuid

    @classmethod
    def get_obj_by_id(cls, _id):
        return cls.get(_id)

    @property
    def is_normal(self):
        return self.state == self.NORMAL

    @property
    def is_archived(self):
        return self.state == self.ARCHIVED

    @property
    def is_deprecated(self):
        return self.state == self.DEPRECATED

    @property
    def is_duplicate(self):
        return self.state == self.DUPLICATE

    @property
    def is_error(self):
        return self.state == self.ERROR

    @property
    def is_submission_error_log(self):
        return self.state == self.SUBMISSION_ERROR_LOG

    @property
    @memoized
    def form_data(self):
        from .utils import convert_xform_to_json, adjust_datetimes
        xml = self.get_xml()
        form_json = convert_xform_to_json(xml)
        adjust_datetimes(form_json)
        return form_json

    @property
    def history(self):
        return self.xformoperationsql_set.order_by('date')

    @property
    def metadata(self):
        from .utils import clean_metadata
        if const.TAG_META in self.form_data:
            return XFormPhoneMetadata.wrap(clean_metadata(self.form_data[const.TAG_META]))

        return None

    def save(self, *args, **kwargs):
        super(XFormInstanceSQL, self).save(*args, **kwargs)
        if getattr(self, 'initial_deprecation', False):
            attachments = XFormAttachmentSQL.objects.filter(xform_id=self.orig_id)
            attachments.update(xform_id=self.form_id)

            operations = XFormOperationSQL.objects.filter(xform_id=self.orig_id)
            operations.update(xform_id=self.form_id)

    def to_json(self):
        from .serializers import XFormInstanceSQLSerializer
        serializer = XFormInstanceSQLSerializer(self)
        return serializer.data

    def get_xml_element(self):
        xml = self.get_xml()
        if not xml:
            return None

        def _to_xml_element(payload):
            if isinstance(payload, unicode):
                payload = payload.encode('utf-8', errors='replace')
            return etree.fromstring(payload)
        return _to_xml_element(xml)

    def get_xml(self):
        return self.get_attachment('form.xml')

    def xml_md5(self):
        return self.get_attachment_meta('form.xml').md5

    def archive(self, user=None):
        if self.is_archived:
            return
        with transaction.atomic():
            self.state = self.ARCHIVED
            self.xformoperationsql_set.create(
                user=user,
                operation=XFormOperationSQL.ARCHIVE,
            )
            self.save()
        xform_archived.send(sender="form_processor", xform=self)

    def unarchive(self, user=None):
        if not self.is_archived:
            return
        with transaction.atomic():
            self.state = self.NORMAL
            self.xformoperationsql_set.create(
                user=user,
                operation=XFormOperationSQL.UNARCHIVE,
            )
            self.save()
        # xform_unarchived.send(sender="form_processor", xform=self)


class AbstractAttachment(models.Model):
    attachment_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    content_type = models.CharField(max_length=255)
    md5 = models.CharField(max_length=255)

    @property
    def filepath(self):
        if getattr(settings, 'IS_TRAVIS', False):
            return os.path.join('/home/travis/', self.attachment_uuid)
        return os.path.join('/tmp/', self.attachment_uuid)

    def write_content(self, content):
        with open(self.filepath, 'w+') as f:
            f.write(content)

    def read_content(self):
        with open(self.filepath, 'r+') as f:
            content = f.read()
        return content

    class Meta:
        abstract = True


class XFormAttachmentSQL(AbstractAttachment):
    xform = models.ForeignKey(
        XFormInstanceSQL, to_field='form_uuid', db_column='form_uuid',
        related_name=AttachmentMixin.ATTACHMENTS_RELATED_NAME, related_query_name="attachment"
    )


class XFormOperationSQL(models.Model):
    ARCHIVE = 'archive'
    UNARCHIVE = 'unarchive'

    user = models.CharField(max_length=255, null=True)
    operation = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    xform = models.ForeignKey(XFormInstanceSQL, to_field='form_uuid')


class XFormPhoneMetadata(jsonobject.JsonObject):
    """
    Metadata of an xform, from a meta block structured like:

        <Meta>
            <timeStart />
            <timeEnd />
            <instanceID />
            <userID />
            <deviceID />
            <username />

            <!-- CommCare extension -->
            <appVersion />
            <location />
        </Meta>

    See spec: https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaMetaDataSchema

    username is not part of the spec but included for convenience
    """

    timeStart = jsonobject.DateTimeProperty()
    timeEnd = jsonobject.DateTimeProperty()
    instanceID = jsonobject.StringProperty()
    userID = jsonobject.StringProperty()
    deviceID = jsonobject.StringProperty()
    username = jsonobject.StringProperty()
    appVersion = jsonobject.StringProperty()
    location = GeoPointProperty()


class CommCareCaseSQL(PreSaveHashableMixin, models.Model, RedisLockableMixIn, AttachmentMixin, AbstractCommCareCase):
    hash_property = 'case_uuid'

    case_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    domain = models.CharField(max_length=255)
    case_type = models.CharField(max_length=255)

    owner_id = models.CharField(max_length=255)

    opened_on = models.DateTimeField(null=False)
    opened_by = models.CharField(max_length=255, null=False)

    modified_on = models.DateTimeField(null=False)
    server_modified_on = models.DateTimeField(null=False)
    modified_by = models.CharField(max_length=255)

    closed = models.BooleanField(default=False, null=False)
    closed_on = models.DateTimeField(null=True)
    closed_by = models.CharField(max_length=255, null=False)

    deleted = models.BooleanField(default=False, null=False)

    external_id = models.CharField(max_length=255)

    case_json = JSONField(lazy=True)

    def __get_case_id(self):
        return self.case_uuid

    def __set_case_id(self, _id):
        self.case_uuid = _id

    case_id = property(__get_case_id, __set_case_id)

    @property
    def user_id(self):
        return self.modified_by

    def hard_delete(self):
        # see cleanup.safe_hard_delete
        raise NotImplementedError()

    def soft_delete(self):
        self.deleted = True
        self.save()

    @property
    def is_deleted(self):
        return self.deleted

    def dynamic_case_properties(self):
        return self.case_json

    def to_json(self):
        from .serializers import CommCareCaseSQLSerializer
        serializer = CommCareCaseSQLSerializer(self)
        return serializer.data

    @property
    @memoized
    def indices(self):
        if hasattr(self, 'unsaved_indices'):
            return self.unsaved_indices

        return self.index_set.all() if self.is_saved() else []

    @classmethod
    def get(cls, case_id):
        return CommCareCaseSQL.objects.get(case_uuid=case_id)

    @classmethod
    def get_cases(cls, ids):
        return CommCareCaseSQL.objects.filter(case_uuid__in=list(ids))

    @classmethod
    def get_case_xform_ids(cls, case_id):
        return CaseForms.objects.filter(case_uuid=case_id)

    @classmethod
    def get_obj_id(cls, obj):
        return obj.case_uuid

    @classmethod
    def get_obj_by_id(cls, _id):
        return cls.get(_id)

    def __unicode__(self):
        return (
            "CommCareCase("
            "case_id='{c.case_uuid}', "
            "domain='{c.domain}', "
            "closed={c.closed}, "
            "owner_id='{c.owner_id}', "
            "server_modified_on='{c.server_modified_on}')"
        ).format(c=self)

    class Meta:
        # TODO SK 2015-11-05: verify that these are the indexes we want
        # also consider partial indexes
        index_together = [
            ["domain", "owner_id"],
            ["domain", "closed", "server_modified_on"],
        ]


class CaseAttachmentSQL(AbstractAttachment):
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=True,
        related_name=AttachmentMixin.ATTACHMENTS_RELATED_NAME, related_query_name="attachment"
    )


class CommCareCaseIndexSQL(models.Model):
    CHILD = 0
    EXTENSION = 1
    RELATIONSHIP_CHOICES = (
        (CHILD, 'child'),
        (EXTENSION, 'extension'),
    )

    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=True,
        related_name="index_set", related_query_name="index"
    )
    domain = models.CharField(max_length=255)  # TODO SK 2015-11-05: is this necessary or should we join on case?
    identifier = models.CharField(max_length=255, null=False)
    referenced_id = models.CharField(max_length=255, null=False)
    referenced_type = models.CharField(max_length=255, null=False)
    relationship = models.PositiveSmallIntegerField(choices=RELATIONSHIP_CHOICES)

    def __unicode__(self):
        return (
            "CaseIndex("
            "case_id='{i.case_uuid}', "
            "domain='{i.domain}', "
            "identifier='{i.identifier}', "
            "referenced_type='{i.referenced_type}', "
            "referenced_id='{i.referenced_id}', "
            "relationship='{i.relationship})"
        ).format(i=self)

    class Meta:
        index_together = [
            ["domain", "referenced_id"],
        ]


class CaseForms(models.Model):
    case = models.ForeignKey('CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=False)
    form_uuid = models.CharField(max_length=255, null=False)  # can't be a foreign key due to partitioning

    class Meta:
        unique_together = ("case", "form_uuid")
