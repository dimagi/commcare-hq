from django.db import models
from corehq.apps.sofabed.exceptions import (
    InvalidFormUpdateException,
    InvalidMetaBlockException,
    InvalidCaseUpdateException
)

MISSING_APP_ID = '_MISSING_APP_ID'


class BaseDataIndex(models.Model):
    id_property = None

    @classmethod
    def get_instance_id(cls, item):
        raise NotImplementedError()

    @classmethod
    def from_instance(cls, instance):
        """
        Factory method for creating these objects from an instance doc
        """
        ret = cls()
        ret.update(instance)
        return ret

    @classmethod
    def create_or_update_from_instance(cls, instance):
        """
        Create or update an object in the database from an CommCareCase
        """
        try:
            val = cls.objects.get(**{cls.id_property: cls.get_instance_id(instance)})
        except cls.DoesNotExist:
            val = cls.from_instance(instance)
            val.save()
        else:
            if not val.matches_exact(instance):
                val.update(instance)
                val.save()

        return val

    def __unicode__(self):
        return "%s: %s" % (self.__class__.__name__, getattr(self, self.id_property))

    class Meta:
        abstract = True


class FormData(BaseDataIndex):
    """
    Data about a form submission.
    """
    id_property = 'instance_id'

    doc_type = models.CharField(max_length=255, db_index=True)
    domain = models.CharField(max_length=255, db_index=True)
    received_on = models.DateTimeField(db_index=True)

    instance_id = models.CharField(unique=True, primary_key=True,
                                   max_length=255)
    time_start = models.DateTimeField()
    time_end = models.DateTimeField(db_index=True)
    duration = models.IntegerField()
    device_id = models.CharField(max_length=255, null=True)
    user_id = models.CharField(max_length=255, null=True, db_index=True)
    username = models.CharField(max_length=255, null=True)
    app_id = models.CharField(max_length=255, null=True, db_index=True)
    xmlns = models.CharField(max_length=1000, null=True, db_index=True)

    @classmethod
    def get_instance_id(cls, instance):
        return instance.get_id

    def update(self, instance):
        """
        Update this object based on an XFormInstance doc
        """
        instance_id = self.get_instance_id(instance)
        if not instance.metadata:
            raise InvalidMetaBlockException(
                "Instance %s didn't have a meta block!" % instance_id)

        if (instance.metadata.instanceID and
                instance.metadata.instanceID != instance_id):
            # we never want to differentiate between these two ids
            raise InvalidMetaBlockException(
                "Instance had doc id (%s) different "
                "from meta instanceID (%s)!" % (
                    instance_id, instance.metadata.instanceID)
            )

        if self.instance_id and self.instance_id != instance_id:
            # we never allow updates to change the instance ID
            raise InvalidFormUpdateException(
                "Tried to update formdata %s with different "
                "instance id %s!" % (self.instance_id, instance_id)
            )

        if not instance.metadata.timeStart or not instance.metadata.timeStart:
            # we don't allow these fields to be empty
            raise InvalidFormUpdateException(
                "No timeStart or timeEnd found in instance %s!" % (
                    instance_id)
            )

        if not instance.received_on:
            # we don't allow this field to be empty
            raise InvalidFormUpdateException(
                "No received_on date found in instance %s!" % (
                    instance_id)
            )

        self.doc_type = instance.doc_type
        self.domain = instance.domain
        self.received_on = instance.received_on

        self.instance_id = instance_id
        self.time_start = instance.metadata.timeStart
        self.time_end = instance.metadata.timeEnd
        td = instance.metadata.timeEnd - instance.metadata.timeStart
        self.duration = td.seconds + td.days * 24 * 3600
        self.device_id = instance.metadata.deviceID
        self.user_id = instance.metadata.userID
        self.username = instance.metadata.username
        self.app_id = instance.app_id or MISSING_APP_ID
        self.xmlns = instance.xmlns

    def matches_exact(self, instance):
        return (
            self.doc_type == instance.doc_type and
            self.domain == instance.domain and
            self.instance_id == instance.get_id and
            self.time_start == instance.metadata.timeStart and
            self.time_end == instance.metadata.timeEnd and
            self.device_id == instance.metadata.deviceID and
            self.user_id == instance.metadata.userID and
            self.username == instance.metadata.username and
            self.xmlns == instance.xmlns and
            self.received_on == instance.received_on and
            self.app_id == (instance.app_id or MISSING_APP_ID)
        )


class CaseData(BaseDataIndex):
    """
    Data about a CommCareCase
    """
    id_property = 'case_id'

    case_id = models.CharField(unique=True, primary_key=True, max_length=255)
    doc_type = models.CharField(max_length=255, db_index=True)
    domain = models.CharField(max_length=255, db_index=True)
    version = models.CharField(max_length=10, db_index=True)
    type = models.CharField(max_length=255, db_index=True)
    closed = models.BooleanField(db_index=True)
    owner_id = models.CharField(max_length=255, db_index=True)
    opened_on = models.DateTimeField(db_index=True)
    opened_by = models.CharField(max_length=255, db_index=True)
    closed_on = models.DateTimeField(db_index=True, null=True)
    closed_by = models.CharField(max_length=255, db_index=True, null=True)
    modified_on = models.DateTimeField(db_index=True)
    modified_by = models.CharField(max_length=255, db_index=True, null=True)
    server_modified_on = models.DateTimeField(db_index=True)
    name = models.CharField(max_length=512)
    external_id = models.CharField(max_length=512, null=True)

    @classmethod
    def get_instance_id(cls, instance):
        return instance.case_id

    def update(self, case):
        """
        Update this object based on a CommCareCase doc
        """
        case_id = self.get_instance_id(case)

        if self.case_id and self.case_id != case_id:
            # we never allow updates to change the instance ID
            raise InvalidCaseUpdateException(
                "Tried to update CaseData %s with different "
                "case id %s!" % (self.case_id, case_id)
            )

        self.case_id = case_id
        self.doc_type = case.doc_type
        self.domain = case.domain
        self.version = case.version
        self.type = case.type
        self.closed = case.closed
        self.owner_id = case.owner_id
        self.opened_on = case.opened_on
        self.opened_by = case.opened_by
        self.closed_on = case.closed_on
        self.closed_by = case.closed_by
        self.modified_on = case.modified_on
        self.modified_by = case.user_id
        self.server_modified_on = case.server_modified_on
        self.name = case.name
        self.external_id = case.external_id

        CaseActionData.objects.filter(case_id=case_id).delete()
        actions = [CaseActionData.from_instance(action, i) for i, action in enumerate(case.actions)]
        self.actions = actions

    def matches_exact(self, case):
        return (
            self.modified_on == case.modified_on and
            self.modified_by == case.user_id and
            self.closed == case.closed and
            self.closed_on == case.closed_on and
            self.closed_by == case.closed_by and
            self.server_modified_on == case.server_modified_on and
            self.case_id == case.case_id and
            self.doc_type == case.doc_type and
            self.domain == case.domain and
            self.version == case.version and
            self.type == case.type and
            self.owner_id == case.owner_id and
            self.opened_on == case.opened_on and
            self.opened_by == case.opened_by and
            self.name == case.name and
            self.external_id == case.external_id
        )

    class Meta:
        ordering = ['opened_on']


class CaseActionData(models.Model):
    """
    Data about a CommCareCase action
    """
    case = models.ForeignKey(CaseData, related_name='actions')
    index = models.IntegerField()
    action_type = models.CharField(max_length=50, db_index=True)
    user_id = models.CharField(max_length=255, db_index=True)
    date = models.DateTimeField(db_index=True)
    server_date = models.DateTimeField()
    xform_id = models.CharField(max_length=255)
    xform_xmlns = models.CharField(max_length=1000, null=True)
    sync_log_id = models.CharField(max_length=255, null=True)

    def __unicode__(self):
        return 'CaseAction: %s(%s)' % (self.case_id, self.index)

    @classmethod
    def from_instance(cls, action, index):
        ret = cls()
        ret.index = index
        ret.action_type = action.action_type
        ret.user_id = action.user_id
        ret.date = action.date
        ret.server_date = action.server_date
        ret.xform_id = action.xform_id
        ret.xform_xmlns = action.xform_xmlns
        ret.sync_log_id = action.sync_log_id
        return ret

    class Meta:
        ordering = ['date']
