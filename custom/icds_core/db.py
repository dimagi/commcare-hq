def create_citus_distributed_table(connection, table, distribution_column):
    res = connection.execute("""
        select 1 from pg_dist_partition
        where partmethod = 'h' and logicalrelid = %s::regclass
    """, [table])
    if res is None:
        res = list(connection)
    if not list(res):
        connection.execute("select create_distributed_table(%s, %s)", [table, distribution_column])


def create_citus_reference_table(connection, table):
    res = connection.execute("""
        select 1 from pg_dist_partition
        where partmethod = 'n' and logicalrelid = %s::regclass
    """, [table])
    if res is None:
        res = list(connection)
    if not list(res):
        connection.execute("select create_reference_table(%s)", [table])
