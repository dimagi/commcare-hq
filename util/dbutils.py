from django.db import connection

def get_column_names(cursor):
    '''Get all column names from a cursor object
       (not including repeats)'''
    return [col[0] for col in cursor.description]

def get_column_names_from_table(table_name):
    '''Get all column names from a table.'''
    # TODO: watch out for sql injection here!
    if is_configured_mysql():
        query =  "describe %s" % table_name
    elif is_configured_postgres():
        # hat tip: http://en.wikibooks.org/wiki/Converting_MySQL_to_PostgreSQL
        query = """
                    SELECT 
                        a.attname AS Field
                    FROM 
                        pg_class c 
                        JOIN pg_attribute a ON a.attrelid = c.oid 
                    WHERE
                        c.relname = '%s'
                        AND a.attnum > 0
                    ORDER BY a.attnum
                """  % table_name
    else:
        raise Exception("Sorry we don't yet support your database configuration!")
    cursor = connection.cursor()
    cursor.execute(query)
    return [col[0] for col in cursor.fetchall()]


def get_column_types_from_table(table_name):
    '''Get all column data types from a table.'''
    if is_configured_mysql():
        query =  "describe %s" % table_name
        index = 1
    elif is_configured_postgres():
        # hat tip: http://en.wikibooks.org/wiki/Converting_MySQL_to_PostgreSQL
        query = """
                    SELECT 
                        t.typname || '(' || a.atttypmod || ')' AS Type
                    FROM 
                        pg_class c 
                        JOIN pg_attribute a ON a.attrelid = c.oid
                        JOIN pg_type t ON a.atttypid = t.oid
                    WHERE
                        c.relname = '%s'
                        AND a.attnum > 0
                    ORDER BY a.attnum
                """  % table_name
        index = 0
    else:
        raise Exception("Sorry we don't yet support your database configuration!")
    
    cursor = connection.cursor()
    # TODO: watch out for sql injection here!
    cursor.execute(query)
    return [col[index] for col in cursor.fetchall()]

def _is_configured(config_func):
    from django.conf import settings
    return config_func(settings.DATABASE_ENGINE)

def is_postgres(db_engine):
    """Whether a database is postgres"""
    return db_engine.startswith('postgresql')

def is_configured_postgres():
    return _is_configured(is_postgres)

def is_mysql(db_engine):
    """Whether a database is mysql"""
    return db_engine == 'mysql'

def is_configured_mysql():
    return _is_configured(is_mysql)

def is_realsql(db_engine):
    """Whether a database is "real" sql"""
    return is_mysql(db_engine) or is_postgres(db_engine)

def is_configured_realsql():
    return _is_configured(is_realsql)
    
