from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
from django.db import connections
from django.db.models import UUIDField, CharField, ForeignKey
from corehq.sql_db.config import partition_config
from corehq.sql_db.util import get_all_sharded_models


class DatabaseShardInfo(object):

    def __init__(self, db):
        self.db = db
        # dicts of shard ID to dicts of model: count
        self._expected_data = {
            shard_id: defaultdict(lambda: 0) for shard_id in partition_config.get_shards_on_db(db)
        }
        self._unexpected_data = defaultdict(lambda: defaultdict(lambda: 0))

    def add_model_data(self, model, shard_data):
        for shard_id, object_count in shard_data:
            if shard_id in self._expected_data:
                self._expected_data[shard_id][model] += object_count
            else:
                self._unexpected_data[shard_id][model] += object_count

    def __str__(self):
        return """
========================================
              {db}

============== Valid Data ==============
{expected_data}

============= Invalid Data =============
{unexpected_data}
        """.format(
            db=self.db,
            expected_data=self._get_formatted_expected_data(),
            unexpected_data=self._get_formatted_unexpected_data(),
        )

    def to_csv(self):
        def _add_to_rows(rows, data, label):
            for shard_id in sorted(data.keys()):
                rows.extend([
                    '{},{},{},{}'.format(shard_id, model.__name__, data[shard_id][model], label)
                    for model in sorted(data[shard_id].keys())
                ])

        rows = []
        _add_to_rows(rows, self._expected_data, 'valid')
        _add_to_rows(rows, self._unexpected_data, 'INVALID')
        return '\n'.join(rows)

    def _get_formatted_expected_data(self):
        return self._get_formatted_data(self._expected_data)

    def _get_formatted_unexpected_data(self):
        return self._get_formatted_data(self._unexpected_data)

    def _get_formatted_data(self, data):
        formatted_rows = []
        for shard_id in sorted(data.keys()):
            formatted_rows.append('')
            formatted_rows.append('--------------- shard {} ---------------'.format(shard_id))
            formatted_rows.extend([
                '{}, {}'.format(model.__name__, data[shard_id][model])
                for model in sorted(data[shard_id].keys())
            ])
        return '\n'.join(formatted_rows)


def get_database_shard_info_for_testing(database):
    sharded_models = list(get_all_sharded_models())
    shard_info = DatabaseShardInfo(database)
    for model in sharded_models:
        data = get_count_of_models_by_shard_for_testing(database, model)
        shard_info.add_model_data(model, data)
    return shard_info


def get_count_of_unmatched_models_by_shard(database, model):
    """
    Get counts of any `model` data residing on shards that aren't expected to live in `database`.

    Returns a list of tuples of the format:
    [
      (shard_id, count_of_unexpected_models),
    ]

    The list will be empty if no invalid data is found.
    """
    cursor = connections[database].cursor()
    query = _get_unmatched_shard_count_query_for_testing(model)
    valid_shards = partition_config.get_shards_on_db(database)
    cursor.execute(query, [valid_shards])
    results = cursor.fetchall()
    return results


def delete_unmatched_shard_data(database, model, query_size=5000):
    """
    Deletes any `model` data residing on shards that aren't expected to live in `database`.

    The deletes are batched in query_size and sorted by the model's partition_attr.

    Returns a generator where each value is a tuple of last value included in the query and number of records deleted
    """
    column_name = model.partition_attr
    shard_id_function = _get_shard_id_function(model)

    # Intentionally uses BETWEEN because it is inclusive of both values
    query = """
    DELETE FROM {table_name}
    WHERE NOT ({shard_id_function}) = ANY(%s) AND {column_name} BETWEEN %s AND %s;
    """.format(
        shard_id_function=shard_id_function,
        table_name=model._meta.db_table,
        column_name=column_name
    )

    valid_shards = partition_config.get_shards_on_db(database)
    qs = model.objects.using(database).order_by(column_name).values_list(column_name, flat=True)
    prev_value = None
    value = qs.first()
    last_value = qs.order_by('-{}'.format(column_name)).first()
    filter_expression = {}

    first_run = True
    while first_run or value < last_value:
        first_run = False
        qs = qs.filter(**filter_expression)
        prev_value = value
        try:
            value = qs[query_size]
        except IndexError:
            # If the queryset has < query_size elements available we can use the last_value
            value = last_value

        with connections[database].cursor() as cursor:
            cursor.execute(query, [valid_shards, prev_value, value])
            num_deleted_count = cursor.rowcount

        # update the filter expression, so the next query begins with the latest value that's been deleted
        filter_expression = {'{}__gt'.format(column_name): value}
        yield value, num_deleted_count


def get_count_of_models_by_shard_for_testing(database, model):
    cursor = connections[database].cursor()
    query = _get_counts_by_shard_query_for_testing(model)
    cursor.execute(query)
    results = cursor.fetchall()
    return results


def _get_unmatched_shard_count_query_for_testing(model):
    # syntax of this query is a bit weird because of a couple django / postgres ARRAY oddities
    # https://stackoverflow.com/a/22008870/8207
    # https://stackoverflow.com/a/11730789/8207
    return """
       select * from ({counts_by_shard_query}

        ) as countsByShard
        where not shard_id = ANY(%s);
    """.format(
        counts_by_shard_query=_get_counts_by_shard_query_for_testing(model),
    )


def _get_counts_by_shard_query_for_testing(model):
    shard_id_function = _get_shard_id_function(model)
    return """
        select {shard_id_function} as shard_id, count(*)
        from {table_name}
        group by shard_id
    """.format(
        shard_id_function=shard_id_function,
        table_name=model._meta.db_table,
    )


def _get_shard_id_function(model):
    # have to cast to varchar because some tables have uuid types
    field_type = model._meta.get_field(model.partition_attr)
    if isinstance(field_type, UUIDField):
        # magic: https://gist.github.com/cdmckay/a82261e48a42a3bbd78a
        return (
            "hash_string(decode(replace({id_field}::text, '-', ''), 'hex'), 'siphash24')"
            " & {total_shard_count}"
        ).format(
            total_shard_count=partition_config.num_shards - 1,
            id_field=model.partition_attr,
        )
    elif _is_a_string_field(field_type):
        return "hash_string({id_field}, 'siphash24') & {total_shard_count}".format(
            total_shard_count=partition_config.num_shards - 1,
            id_field=model.partition_attr,
        )
    raise Exception('Tried to shard based on an unexpected field type: {}'.format(type(field_type)))


def _is_a_string_field(field_type):
    return (
        isinstance(field_type, CharField)
        or (isinstance(field_type, ForeignKey) and isinstance(field_type.target_field, CharField))
    )
