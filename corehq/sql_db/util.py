from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
from corehq.sql_db.config import partition_config
from django.conf import settings


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


def run_query_across_partitioned_databases(model_class, q_expression, values=None):
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

    :return: A generator with the results
    """
    db_names = get_db_aliases_for_partitioned_query()

    if values and not isinstance(values, (list, tuple)):
        raise ValueError("Expected a list or tuple")

    for db_name in db_names:
        qs = model_class.objects.using(db_name).filter(q_expression)
        if values:
            if len(values) == 1:
                qs = qs.values_list(*values, flat=True)
            else:
                qs = qs.values_list(*values)

        for result in qs:
            yield result


def get_db_alias_for_partitioned_doc(partition_value):
    if settings.USE_PARTITIONED_DATABASE:
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
