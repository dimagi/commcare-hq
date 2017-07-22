import uuid
from corehq.sql_db.config import partition_config
from django.conf import settings
from django import db
from django.db.utils import InterfaceError as DjangoInterfaceError
from functools import wraps
from psycopg2._psycopg import InterfaceError as Psycopg2InterfaceError


def get_object_from_partitioned_database(model_class, partition_value, lookup_field_name, lookup_value):
    """
    Determines from which database to retrieve a paritioned model object and
    retrieves it.

    :param model_class: A Django model class

    :param parition_value: The value that is used to partition the model; this
    value will be used to select the database

    :param lookup_field_name: The model field on which to lookup the object

    :param lookup_value: The value for which to lookup the object

    :return: The model object
    """
    db_name = get_db_alias_for_partitioned_doc(partition_value)
    kwargs = {
        lookup_field_name: lookup_value,
    }
    return model_class.objects.using(db_name).get(**kwargs)


def save_object_to_partitioned_database(obj, partition_value):
    """
    Determines to which database to save a partitioned model object and
    saves it there.

    :param obj: A Django model object

    :param parition_value: The value that is used to partition the model; this
    value will be used to select the database
    """
    db_name = get_db_alias_for_partitioned_doc(partition_value)
    obj.save(using=db_name)


def delete_object_from_partitioned_database(obj, partition_value):
    """
    Determines from which database to delete a partitioned model object and
    deletes it there.

    :param obj: A Django model object

    :param parition_value: The value that is used to partition the model; this
    value will be used to select the database
    """
    db_name = get_db_alias_for_partitioned_doc(partition_value)
    obj.delete(using=db_name)


def run_query_across_partitioned_databases(model_class, q_expression, values=None, annotate=None):
    """
    Runs a query across all partitioned databases and produces a generator
    with the results.

    :param model_class: A Django model class

    :param q_expression: An instance of django.db.models.Q representing the
    filter to apply

    :param values: (optional) If specified, should be a list of values to retrieve rather
    than retrieving entire objects. If a list with a single value is given, the result will
    be a generator of single values. If a list with multiple values is given, the result
    will be a generator of tuples.

    :param annotate: (optional) If specified, should by a dictionary of annotated fields
    and their calculations. The dictionary will be splatted into the `.annotate` function

    :return: A generator with the results
    """
    db_names = get_db_aliases_for_partitioned_query()

    if values and not isinstance(values, (list, tuple)):
        raise ValueError("Expected a list or tuple")

    for db_name in db_names:
        qs = model_class.objects.using(db_name)
        if annotate:
            qs = qs.annotate(**annotate)

        qs = qs.filter(q_expression)
        if values:
            if len(values) == 1:
                qs = qs.values_list(*values, flat=True)
            else:
                qs = qs.values_list(*values)

        for result in qs:
            yield result


def get_db_alias_for_partitioned_doc(partition_value):
    if settings.USE_PARTITIONED_DATABASE:
        from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
        db_name = ShardAccessor.get_database_for_doc(partition_value)
    else:
        db_name = 'default'
    return db_name


def new_id_in_same_dbalias(partition_value):
    """
    Returns a new partition value that belongs to the same db alias as
        the given partition value does
    """
    old_db_name = get_db_alias_for_partitioned_doc(partition_value)
    new_db_name = None
    while old_db_name != new_db_name:
        # todo; guard against infinite recursion
        new_partition_value = unicode(uuid.uuid4())
        new_db_name = get_db_alias_for_partitioned_doc(new_partition_value)
    return new_partition_value


def get_db_aliases_for_partitioned_query():
    if settings.USE_PARTITIONED_DATABASE:
        db_names = partition_config.get_form_processing_dbs()
    else:
        db_names = ['default']
    return db_names


def get_default_db_aliases():
    return ['default']


def get_default_and_partitioned_db_aliases():
    return list(set(get_db_aliases_for_partitioned_query() + get_default_db_aliases()))


def handle_connection_failure(get_db_aliases=get_default_db_aliases):
    def _inner2(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except db.utils.DatabaseError:
                # we have to do this manually to avoid issues with
                # open transactions and already closed connections
                for db_name in get_db_aliases():
                    db.transaction.rollback(using=db_name)

                # re raise the exception for additional error handling
                raise
            except (Psycopg2InterfaceError, DjangoInterfaceError):
                # force closing the connection to prevent Django from trying to reuse it.
                # http://www.tryolabs.com/Blog/2014/02/12/long-time-running-process-and-django-orm/
                for db_name in get_db_aliases():
                    db.connections[db_name].close()

                # re raise the exception for additional error handling
                raise

        return _inner

    return _inner2
