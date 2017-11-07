from __future__ import absolute_import
from django.db import connections
from corehq.sql_db.config import partition_config


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
    query = _get_shard_count_query(model)
    valid_shards = partition_config.get_shards_on_db(database)
    cursor.execute(query, [valid_shards])
    results = cursor.fetchall()
    return results


def _get_shard_count_query(model):
    # have to cast to varchar because some tables have uuid types
    shard_id_function = "hash_string({id_field}::varchar, 'siphash24') & {total_shard_count}".format(
        total_shard_count=partition_config.num_shards - 1,
        id_field=model.partition_attr,
    )
    # syntax of this query is a bit weird because of a couple django / postgres ARRAY oddities
    # https://stackoverflow.com/a/22008870/8207
    # https://stackoverflow.com/a/11730789/8207
    return """
       select * from (
           select {shard_id_function} as shard_id, count(*)
           from {table_name}
           group by shard_id
        ) as countsByShard
        where shard_id <> ANY(%s);
    """.format(
        shard_id_function=shard_id_function,
        table_name=model._meta.db_table,
    )
