import sys

from django.db.models import CharField


class ModelClassField(CharField):
    """Stores a slug in the DB but reads/writes Django model classes.

    Lets callers query and assign with the class itself, e.g.
    ``filter(model=XFormInstance)``.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 128)
        super().__init__(*args, **kwargs)

    @property
    def _slug_by_model(self):
        from corehq.form_processor.models import CommCareCase, XFormInstance

        return {CommCareCase: 'case', XFormInstance: 'xform'}

    @property
    def _model_by_slug(self):
        return {v: k for k, v in self._slug_by_model.items()}

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self._model_by_slug[value]

    def to_python(self, value):
        if value is None or value in self._slug_by_model:
            return value
        return self._model_by_slug[value]

    def get_prep_value(self, value):
        if value is None or isinstance(value, str):
            return value
        return self._slug_by_model[value]

    def pre_save(self, model_instance, add):
        # This field's value is a model class, and every Django model has a
        # prepare_database_save method. The UPDATE compiler treats any value with
        # that method as a related-object assignment; since this isn't a relation it
        # rejects the value before it would convert it. Return the slug so
        # UPDATE sees a plain string, like every other column.
        return self.get_prep_value(getattr(model_instance, self.attname))


class CharIdField(CharField):
    """CharField that does not create varchar_pattern_ops index

    Django automatically creates varchar_pattern_ops indexes for indexed
    varchar columns to support `LIKE` and regular expression queries. ID
    fields are not typically quieried with those operators, and
    therefore the extra index would degrade performance and consume
    storage for no benefit.
    """

    def db_type(self, connection):
        # HACK short circuit index creation based on caller name
        if _get_caller_name() == "_create_like_index_sql":
            return None
        return super().db_type(connection)


def _get_caller_name():
    return sys._getframe(2).f_code.co_name
