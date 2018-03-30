from __future__ import absolute_import
from __future__ import unicode_literals
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

    @staticmethod
    def get_db(partition_value):
        from corehq.sql_db.util import get_db_alias_for_partitioned_doc
        return get_db_alias_for_partitioned_doc(partition_value)

    def partitioned_get(self, partition_value, **kwargs):
        """Get a partioned model from it's database

        If the lookup should be performed using a different lookup value then it
        should be supplied as a keyword argument:

            model.objects.partitioned_get(partition_value, other_field=value)

        is equivalent to:

            db = get_db_alias_for_partitioned_doc(partition_value)
            model.objects.using(db).get(other_field=value)

        :param partition_value: The value that is used to partition the model;
                                this value will be used to select the database
        """
        if not kwargs:
            kwargs = {
                self.model.partition_attr: partition_value
            }
        return self.using(self.get_db(partition_value)).get(**kwargs)

    def partitioned_query(self, partition_value):
        """Shortcut to get a queryset for a partitioned database.
        Equivalent to:

            db = get_db_alias_for_partitioned_doc(partition_value)
            qs = Model.objects.using(db)
        """
        return self.using(self.get_db(partition_value))


class PartitionedModel(models.Model):
    """
    This makes it so that you must specify a database name when
    using model methods .save() and .delete(), or when running
    queries through the model Manager.

    Useful to prevent accidental queries with Models whose partitioning
    is determined in Python rather than PL/Proxy.
    """

    objects = RequireDBManager()

    @property
    def partition_attr(self):
        raise NotImplementedError

    @property
    def partition_value(self):
        return getattr(self, self.partition_attr)

    @property
    def db(self):
        """The partitioned database for this object"""
        assert self.partition_value, 'Partitioned model must have a partition value'
        return RequireDBManager.get_db(self.partition_value)

    class Meta(object):
        abstract = True

    def save(self, *args, **kwargs):
        self._add_routing(kwargs)
        return super(PartitionedModel, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._add_routing(kwargs)
        return super(PartitionedModel, self).delete(*args, **kwargs)

    def _add_routing(self, kwargs):
        if 'using' in kwargs:
            assert kwargs['using'] == self.db
        else:
            kwargs['using'] = self.db
