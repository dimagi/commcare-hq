from couchdbkit.resource import ResourceNotFound
from dimagi.utils.logging import notify_exception


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

    2. Make the Couch model inherit from SyncCouchToSQLMixin.

    3. Implement the unimplemented methods from the mixins on both models.

    4. Make sure neither of the models overrides the save() method. If
    either does, you will have to manually insert the sync code from
    the corresponding mixin. Also make sure the mixins are the left-most
    classes being inherited from.

    After that, any saves to the Couch model will sync the SQL model, and
    any saves to the SQL model will sync the Couch model. After migrating
    each doc, you can incrementally change the code to use to SQL model
    instead of the Couch model, and eventually remove the Couch model entirely.

    If you have a custom sync process, just override _migration_sync_to_sql.
    """

    @classmethod
    def _migration_get_fields(cls):
        """
        Should return a list of field names to sync. These field names should
        be identical between the Couch and SQL models.
        """
        raise NotImplementedError()

    @classmethod
    def _migration_get_sql_model_class(cls):
        """
        Should return the class of the SQL model.
        """
        raise NotImplementedError()

    def _migration_get_or_create_sql_object(self):
        cls = self._migration_get_sql_model_class()
        try:
            obj = cls.objects.get(couch_id=self._id)
        except cls.DoesNotExist:
            obj = cls(couch_id=self._id)
        return obj

    def _migration_sync_to_sql(self, sql_object):
        for field_name in self._migration_get_fields():
            value = getattr(self, field_name)
            setattr(sql_object, field_name, value)
        sql_object.save(sync_to_couch=False)

    def _migration_do_sync(self):
        sql_object = self._migration_get_or_create_sql_object()
        self._migration_sync_to_sql(sql_object)

    def save(self, *args, **kwargs):
        sync_to_sql = kwargs.pop('sync_to_sql', True)
        super(SyncCouchToSQLMixin, self).save(*args, **kwargs)
        if sync_to_sql:
            try:
                self._migration_do_sync()
            except:
                sql_class_name = self._migration_get_sql_model_class().__name__
                couch_class_name = self.__class__.__name__
                notify_exception(None,
                    message='Could not sync %s SQL object from %s %s' % (sql_class_name,
                        couch_class_name, self._id))


class SyncSQLToCouchMixin(object):
    """
    See SyncCouchToSQLMixin.

    If you have a custom sync process, just override _migration_sync_to_couch.
    """

    @classmethod
    def _migration_get_fields(cls):
        """
        Should return a list of field names to sync. These field names should
        be identical between the Couch and SQL models.
        """
        raise NotImplementedError()

    @classmethod
    def _migration_get_couch_model_class(cls):
        """
        Should return the class of the Couch model.
        """
        raise NotImplementedError()

    def _migration_get_or_create_couch_object(self):
        cls = self._migration_get_couch_model_class()
        if not self.couch_id:
            obj = cls()
            obj.save()
            self.couch_id = obj._id
            self.save(sync_to_couch=False)
        else:
            obj = cls.get(self.couch_id)

        return obj

    def _migration_sync_to_couch(self, couch_obj):
        for field_name in self._migration_get_fields():
            value = getattr(self, field_name)
            setattr(couch_obj, field_name, value)
        couch_obj.save(sync_to_sql=False)

    def _migration_do_sync(self):
        couch_obj = self._migration_get_or_create_couch_object()
        self._migration_sync_to_couch(couch_obj)

    def save(self, *args, **kwargs):
        sync_to_couch = kwargs.pop('sync_to_couch', True)
        super(SyncSQLToCouchMixin, self).save(*args, **kwargs)
        if sync_to_couch:
            try:
                self._migration_do_sync()
            except:
                couch_class_name = self._migration_get_couch_model_class().__name__
                sql_class_name = self.__class__.__name__
                notify_exception(None,
                    message='Could not sync %s Couch object from %s %s' % (couch_class_name,
                        sql_class_name, self.pk))
