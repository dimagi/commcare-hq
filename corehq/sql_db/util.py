from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from collections import defaultdict

from corehq.sql_db.config import partition_config
from django.conf import settings
from django import db
from django.db.utils import InterfaceError as DjangoInterfaceError
from functools import wraps
from psycopg2._psycopg import InterfaceError as Psycopg2InterfaceError
import six
from corehq.sql_db.models import PartitionedModel


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


def split_list_by_db_partition(partition_values):
    """
    :param partition_values: Iterable of partition values (e.g. case IDs)
    :return: list of tuples (db_name, list(partition_values))
    """
    mapping = defaultdict(list)
    for value in partition_values:
        db_name = get_db_alias_for_partitioned_doc(value)
        mapping[db_name].append(value)
    return list(mapping.items())


def get_db_alias_for_partitioned_doc(partition_value):
    if settings.USE_PARTITIONED_DATABASE:
        from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
        db_name = ShardAccessor.get_database_for_doc(partition_value)
    else:
        db_name = 'default'
    return db_name


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


def new_id_in_same_dbalias(partition_value):
    """
    Returns a new partition value that belongs to the same db alias as
        the given partition value does
    """
    old_db_name = get_db_alias_for_partitioned_doc(partition_value)
    new_db_name = None
    while old_db_name != new_db_name:
        # todo; guard against infinite recursion
        new_partition_value = six.text_type(uuid.uuid4())
        new_db_name = get_db_alias_for_partitioned_doc(new_partition_value)
    return new_partition_value


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


def get_all_sharded_models():
    for subclass in _get_all_nested_subclasses(PartitionedModel):
        if not subclass._meta.abstract:
            yield subclass


def _get_all_nested_subclasses(cls):
    seen = set()
    for subclass in cls.__subclasses__():
        for sub_subclass in _get_all_nested_subclasses(subclass):
            # in case of multiple inheritance
            if sub_subclass not in seen:
                seen.add(sub_subclass)
                yield sub_subclass
        if subclass not in seen:
            seen.add(subclass)
            yield subclass
