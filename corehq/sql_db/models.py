from corehq.util.exceptions import AccessRestricted
from django.db import models


def raise_access_restricted():
    raise AccessRestricted("This model can be partitioned. Please specify which"
        "partitioned database with `using` or look for an appropriate dbaccessors "
        "method.")


class RequireDBQuerySet(object):
    """
    Takes a QuerySet when instantiated. If .using() is called on this object,
    it will return the queryset with the given database selected. If anything
    else is called on this object, it will raise AccessRestricted.
    """

    def __init__(self, queryset):
        self.queryset = queryset

    def using(self, db_name):
        return self.queryset.using(db_name)

    def __getattr__(self, item):
        raise_access_restricted()

    def __iter__(self):
        raise_access_restricted()

    def __len__(self):
        raise_access_restricted()

    def __getitem__(self, key):
        raise_access_restricted()


class RequireDBManager(models.Manager):
    """
    A Model Manager which requires that .using() is called before any
    other methods like .filter() or .get().
    """

    def get_queryset(self):
        queryset = super(RequireDBManager, self).get_queryset()
        return RequireDBQuerySet(queryset)


class PartitionedModel(models.Model):
    """
    This makes it so that you must specify a database name when
    using model methods .save() and .delete(), or when running
    queries through the model Manager.

    Useful to prevent accidental queries with Models whose partitioning
    is determined in Python rather than PL/Proxy.
    """

    objects = RequireDBManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not kwargs.get('using'):
            raise_access_restricted()

        return super(PartitionedModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not kwargs.get('using'):
            raise_access_restricted()

        return super(PartitionedModel, self).delete(*args, **kwargs)
