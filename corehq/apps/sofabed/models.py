from django.db import models
from corehq.apps.sofabed.exceptions import (
    InvalidFormUpdateException,
    InvalidMetaBlockException,
    InvalidCaseUpdateException,
    InvalidDomainException)

CASE_NAME_LEN = 512

MISSING_APP_ID = '_MISSING_APP_ID'


class BaseDataIndex(models.Model):

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
            val = cls.objects.get(pk=cls.get_instance_id(instance))
        except cls.DoesNotExist:
            val = cls.from_instance(instance)
            val.save()
        else:
            if not val.matches_exact(instance):
                val.update(instance)
                val.save()

        return val

    def __unicode__(self):
        return "%s: %s" % (self.__class__.__name__, self.pk)

    class Meta:
        abstract = True
