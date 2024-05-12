import threading
from collections import namedtuple
from contextlib import contextmanager

from django.conf import settings

from couchdbkit import ResourceNotFound

from dimagi.utils.logging import notify_exception

_thread_local = threading.local()


@contextmanager
def disable_sync_to_couch(sql_class):
    """Context manager used to disable syncing models from SQL
    to Couch via `model.save`. This is necessary to prevent
    syncs from happening when using functions like `Model.objects.create_or_update`
    """
    if not hasattr(_thread_local, "disabled_models"):
        _thread_local.disabled_models = set()

    _thread_local.disabled_models.add(sql_class)
    try:
        yield
    finally:
        _thread_local.disabled_models.remove(sql_class)


def sync_to_couch_enabled(sql_class):
    return sql_class not in getattr(_thread_local, "disabled_models", set())


SubModelSpec = namedtuple('SubModelSpec', [
    'sql_attr',
    'sql_class',
    'sql_fields',
    'couch_attr',
    'couch_class',
    'couch_fields',
])


class SyncCouchToSQLMixin(object):
    """
    A mixin to be used for migrating a Couch model
    to a SQL model (see also SyncSQLToCouchMixin).

    Steps to use it:

    1. Create a Django ORM model which inherits from SyncSQLToCouchMixin
    and is identical to the Couch model with one additional field named
    couch_id, for the _id of the Couch doc. Make sure you index couch_id
    and allow it to be null since it can be initially null. Do not include
    this field in _migration_get_fields().
    You can override '_migration_couch_id_name' if `couch_id` won't work.
    Note that you cannot set '_migration_couch_id' to the SQL 'id' field.

    2. Make the Couch model inherit from SyncCouchToSQLMixin.

    3. Implement the unimplemented methods from the mixins on both models.

    4. Make sure neither of the models overrides the save() or delete()
    methods. If either does, you will have to manually insert the sync
    code from the corresponding mixin. Also make sure the mixins are the
    left-most classes being inherited from.

    After that, any saves to the Couch model will sync the SQL model, and
    any saves to the SQL model will sync the Couch model. After migrating
    each doc, you can incrementally change the code to use to SQL model
    instead of the Couch model, and eventually remove the Couch model entirely.

    If you have a custom sync process, just override `_migration_get_custom_functions` to
    pass additional migration functions or override _migration_sync_to_sql for a completely
    custom migration.
    """

    @classmethod
    def _migration_get_fields(cls):
        """
        Should return a list of field names to sync. These field names should
        be identical between the Couch and SQL models.
        """
        raise NotImplementedError()

    @classmethod
    def _migration_get_submodels(cls):
        """
        Should return a list of SubModelSpec tuples, one for each SchemaListProperty
        in the couch class. Should be identical in the couch and sql mixins.
        """
        return []

    @classmethod
    def _migration_get_custom_couch_to_sql_functions(cls):
        """
        Should return a list of functions with args: (couch_object, sql_object)
        These will be called in turn when syncing couch model to SQL
        """
        return []

    @classmethod
    def _migration_get_sql_model_class(cls):
        """
        Should return the class of the SQL model.
        """
        raise NotImplementedError()

    def _migration_automatically_handle_dups(self):
        """
        Ideally, you should use a CriticalSection to lock out your get and save
        functionality so that each sync will automatically be atomic. However,
        even after doing so, during periods of high latency the locks may time
        out and you still might end up with a race condition in the sync that
        creates more than one SQL model from this couch model.

        Make this method return True if you want subsequent syncs to delete
        the duplicate records and resync. Otherwise, the default behavior is
        that a notify exception email will go out each time duplicates are found.
        """
        return False

    def _migration_get_sql_object(self):
        cls = self._migration_get_sql_model_class()
        try:
            return cls.objects.get(**{cls._migration_couch_id_name: self._id})
        except cls.DoesNotExist:
            return None
        except cls.MultipleObjectsReturned:
            if not self._migration_automatically_handle_dups():
                raise
            cls.objects.filter(**{cls._migration_couch_id_name: self._id}).delete()
            return None

    def _migration_get_or_create_sql_object(self):
        cls = self._migration_get_sql_model_class()
        obj = self._migration_get_sql_object()
        if obj is None:
            obj = cls(**{cls._migration_couch_id_name: self._id})
        return obj

    def _migration_sync_to_sql(self, sql_object, save=True):
        """Copy data from the Couch model to the SQL model and save it"""
        for field_name in self._migration_get_fields():
            value = getattr(self, field_name)
            setattr(sql_object, field_name, value)
        self._migration_sync_submodels_to_sql(sql_object)
        for custom_func in self._migration_get_custom_couch_to_sql_functions():
            custom_func(self, sql_object)
        if save:
            sql_object.save(sync_to_couch=False)

    def _migration_sync_submodels_to_sql(self, sql_object):
        """Migrate submodels from the Couch model to the SQL model. This is called
        as part of ``_migration_sync_to_sql``"""
        new_submodels = sql_object._new_submodels = {}
        for spec in self._migration_get_submodels():
            manager = getattr(sql_object, spec.sql_attr)
            parent_attr = manager.field.name
            sql_submodels = []
            for couch_submodel in getattr(self, spec.couch_attr):
                obj = spec.sql_class(**{
                    sql_field: getattr(couch_submodel, couch_field)
                    for couch_field, sql_field in zip(spec.couch_fields, spec.sql_fields)
                })
                setattr(obj, parent_attr, sql_object)
                sql_submodels.append(obj)
            new_submodels[spec.sql_class] = sql_submodels, manager

    def _migration_do_sync(self):
        sql_object = self._migration_get_or_create_sql_object()
        self._migration_sync_to_sql(sql_object)
        return sql_object

    def save(self, *args, sync_to_sql=True, **kwargs):
        super(SyncCouchToSQLMixin, self).save(*args, **kwargs)
        if sync_to_sql:
            try:
                self._migration_do_sync()
            except Exception as e:
                if settings.UNIT_TESTING:
                    raise e
                sql_class_name = self._migration_get_sql_model_class().__name__
                couch_class_name = self.__class__.__name__
                notify_exception(None,
                    message='Could not sync %s SQL object from %s %s' % (sql_class_name,
                        couch_class_name, self._id))

    def delete(self, sync_to_sql=True, *args, **kwargs):
        if sync_to_sql:
            sql_object = self._migration_get_sql_object()
            if sql_object is not None:
                sql_object.delete(sync_to_couch=False)
        super(SyncCouchToSQLMixin, self).delete(*args, **kwargs)


class SyncSQLToCouchMixin(object):
    """
    See SyncCouchToSQLMixin.

    If you have a custom sync process, just override _migration_sync_to_couch.
    """
    _migration_couch_id_name = "couch_id"

    @property
    def _migration_couch_id(self):
        return getattr(self, self._migration_couch_id_name)

    @_migration_couch_id.setter
    def _migration_couch_id(self, value):
        setattr(self, self._migration_couch_id_name, value)

    @classmethod
    def _migration_get_fields(cls):
        """
        Should return a list of field names to sync. These field names should
        be identical between the Couch and SQL models.
        """
        raise NotImplementedError()

    @classmethod
    def _migration_get_submodels(cls):
        """
        Should return a list of SubModelSpec tuples, one for each SchemaListProperty
        in the couch class. Should be identical in the couch and sql mixins.
        """
        return cls._migration_get_couch_model_class()._migration_get_submodels()

    @classmethod
    def _migration_get_custom_sql_to_couch_functions(cls):
        """
        Should return a list of functions with args: (sql_object, couch_object)
        These will be called in turn when syncing SQL model to couch
        """
        return []

    @classmethod
    def _migration_get_couch_model_class(cls):
        """
        Should return the class of the Couch model.
        """
        raise NotImplementedError()

    def _migration_get_couch_object(self, **kw):
        if not self._migration_couch_id:
            return None
        cls = self._migration_get_couch_model_class()
        try:
            return cls.get(str(self._migration_couch_id), **kw)
        except ResourceNotFound:
            return None

    def _migration_get_or_create_couch_object(self):
        cls = self._migration_get_couch_model_class()
        obj = self._migration_get_couch_object()
        if obj is None:
            obj = cls()
            obj.save(sync_to_sql=False)
            self._migration_couch_id = obj._id
            self.save(sync_to_couch=False)
        return obj

    def _migration_sync_to_couch(self, couch_object, save=True):
        """Copy data from the SQL model to the Couch model and save it"""
        for field_name in self._migration_get_fields():
            value = getattr(self, field_name)
            setattr(couch_object, field_name, value)
        self._migration_sync_submodels_to_couch(couch_object)
        for custom_func in self._migration_get_custom_sql_to_couch_functions():
            custom_func(self, couch_object)
        if save:
            couch_object.save(sync_to_sql=False)

    def _migration_sync_submodels_to_couch(self, couch_object):
        """Migrate submodels from the SQL model to the Couch model. This is called
        as part of ``_migration_sync_to_couch``"""
        for spec in self._migration_get_submodels():
            couch_submodels = []
            for sql_submodel in getattr(self, spec.sql_attr).all():
                couch_fields = {
                    couch_field: getattr(sql_submodel, sql_field)
                    for couch_field, sql_field in zip(spec.couch_fields, spec.sql_fields)
                }
                couch_submodels.append(spec.couch_class(**couch_fields))
            setattr(couch_object, spec.couch_attr, couch_submodels)

    def _migration_do_sync(self):
        couch_object = self._migration_get_or_create_couch_object()
        self._migration_sync_to_couch(couch_object)

    def save(self, *args, sync_to_couch=True, **kwargs):
        is_update = not self._state.adding
        super(SyncSQLToCouchMixin, self).save(*args, **kwargs)
        self._save_submodels(is_update)
        if sync_to_couch and sync_to_couch_enabled(self.__class__):
            try:
                self._migration_do_sync()
            except Exception as e:
                if settings.UNIT_TESTING:
                    raise e
                couch_class_name = self._migration_get_couch_model_class().__name__
                sql_class_name = self.__class__.__name__
                notify_exception(None,
                    message='Could not sync %s Couch object from %s %s' % (couch_class_name,
                        sql_class_name, self.pk))

    def _save_submodels(self, is_update):
        for sql_class, (objs, manager) in self.__dict__.pop("_new_submodels", {}).items():
            if is_update:
                manager.all().delete()
            sql_class.objects.bulk_create(objs)

    def delete(self, *args, sync_to_couch=True, **kwargs):
        if sync_to_couch and sync_to_couch_enabled(self.__class__):
            couch_object = self._migration_get_couch_object()
            if couch_object is not None:
                couch_object.delete(sync_to_sql=False)
        super(SyncSQLToCouchMixin, self).delete(*args, **kwargs)
