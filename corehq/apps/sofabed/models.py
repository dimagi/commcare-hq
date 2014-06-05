from django.db import models
from corehq.apps.sofabed.exceptions import (
    InvalidFormUpdateException,
    InvalidMetaBlockException,
)

MISSING_APP_ID = '_MISSING_APP_ID'


class FormData(models.Model):
    """
    Data about a form submission.
    """

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

    def __unicode__(self):
        return "FormData: %s" % self.instance_id

    def update(self, instance):
        """
        Update this object based on an XFormInstance doc
        """
        if not instance.metadata:
            raise InvalidMetaBlockException(
                "Instance %s didn't have a meta block!" % instance.get_id)

        if (instance.metadata.instanceID and
                instance.metadata.instanceID != instance.get_id):
            # we never want to differentiate between these two ids
            raise InvalidMetaBlockException(
                "Instance had doc id (%s) different "
                "from meta instanceID (%s)!" % (
                    instance.get_id, instance.metadata.instanceID)
            )

        if self.instance_id and self.instance_id != instance.get_id:
            # we never allow updates to change the instance ID
            raise InvalidFormUpdateException(
                "Tried to update formdata %s with different "
                "instance id %s!" % (self.instance_id, instance.get_id)
            )

        if not instance.metadata.timeStart or not instance.metadata.timeStart:
            # we don't allow these fields to be empty
            raise InvalidFormUpdateException(
                "No timeStart or timeEnd found in instance %s!" % (
                    instance.get_id)
            )

        if not instance.received_on:
            # we don't allow this field to be empty
            raise InvalidFormUpdateException(
                "No received_on date found in instance %s!" % (
                    instance.get_id)
            )

        self.doc_type = instance.doc_type
        self.domain = instance.domain
        self.received_on = instance.received_on

        self.instance_id = instance.get_id
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

    @classmethod
    def from_xforminstance(cls, instance):
        """
        Factory method for creating these objects from XFormInstance docs
        """
        ret = cls()
        ret.update(instance)
        return ret

    @classmethod
    def create_or_update_from_xforminstance(cls, instance):
        """
        Create or update an object in the database from an XFormInstance
        """
        try:
            val = cls.objects.get(instance_id=instance.get_id)
        except cls.DoesNotExist:
            val = cls()

        if not val.matches_exact(instance):
            val.update(instance)
            val.save()

        return val
