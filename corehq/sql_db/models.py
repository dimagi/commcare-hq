from django.db import connections, models, router
from django.db.models.query import RawQuerySet

from corehq.sql_db.routers import (
    HINT_PARTITION_VALUE,
    HINT_PLPROXY,
    HINT_USING,
)
from corehq.util.exceptions import AccessRestricted


def raise_access_restricted(queryset):
    if not queryset._db and 'partition_value' not in queryset._hints and 'using' not in queryset._hints:
        raise AccessRestricted("This model can be partitioned. Please specify which "
            "partitioned database with `using` or look for an appropriate dbaccessors "
            "method.")


class RequireDBManager(models.Manager):
    """
    A Model Manager which requires that .using() is called before any
    other methods like .filter() or .get().
    """

    def get_queryset(self):
        queryset = super(RequireDBManager, self).get_queryset()
        raise_access_restricted(queryset)
        return queryset

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
        return self.partitioned_query(partition_value).get(**kwargs)

    def partitioned_query(self, partition_value=None):
        """Shortcut to get a queryset for a partitioned database.
        Equivalent to:

            db = get_db_alias_for_partitioned_doc(partition_value)
            qs = Model.objects.using(db)
        """
        return self.db_manager(hints={HINT_PARTITION_VALUE: partition_value})

    def using(self, alias):
        return self.db_manager(hints={HINT_USING: alias}).get_queryset()

    def raw(self, raw_query, params=None, translations=None, using=None):
        if using:
            hints = {HINT_USING: using}
        else:
            hints = {HINT_PLPROXY: True}
        return RawQuerySet(raw_query, model=self.model, params=params, translations=translations, hints=hints)

    def plproxy_raw(self, raw_query, params=None):
        return self.raw(raw_query, params)


def _get_cursor(cls, readonly=False, hints=None):
    hints = hints or {}
    action = router.db_for_read if readonly else router.db_for_write
    db = action(cls, **hints)
    return connections[db].cursor()


class PartitionedModel(models.Model):
    """
    This makes it so that you must specify a database name when
    using model methods .save() and .delete(), or when running
    queries through the model Manager.

    Useful to prevent accidental queries with Models whose partitioning
    is determined in Python rather than PL/Proxy.
    """

    objects = RequireDBManager()

    @classmethod
    def get_plproxy_cursor(cls, readonly=False):
        return _get_cursor(cls, readonly, {HINT_PLPROXY: True})

    @classmethod
    def get_cursor_for_partition_value(cls, partition_value, readonly=False):
        return _get_cursor(cls, readonly, {HINT_PARTITION_VALUE: partition_value})

    @classmethod
    def get_cursor_for_partition_db(cls, db_alias, readonly=False):
        return _get_cursor(cls, readonly, {HINT_USING: db_alias})

    @property
    def partition_attr(self):
        raise NotImplementedError

    @property
    def partition_value(self):
        if self.partition_attr not in self.__dict__ and self.pk is None:
            # prevent infinite recursion in db router
            raise AttributeError(
                f"unknown partition value for unsaved {type(self).__name__}")
        return getattr(self, self.partition_attr)

    @property
    def db(self):
        """The partitioned database for this object"""
        assert self.partition_value, 'Partitioned model must have a partition value'
        return RequireDBManager.get_db(self.partition_value)

    class Meta(object):
        abstract = True
