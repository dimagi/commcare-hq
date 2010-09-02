from django.db import connection
import logging

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

def _setup_xform_settings(settings):
    import django
    if django.VERSION[0:3] == (1,2,1):
        if hasattr(settings, 'DATABASE_ENGINE'):
            logging.error("You are running django 1.2.1, but your database settings reflect the old style single database, please use the updated settings format for databases.")
            #this is hacky too, we're just assuming default until we get a more strategic multidb setup.
        default_db = settings.DATABASES['default']
        settings.XFORMS_DATABASE_ENGINE=default_db['ENGINE'].split('.')[-1]
        settings.XFORMS_DATABASE_OPTIONS = default_db['OPTIONS']        
    else:
        logging.error("You are using an older version of django, please upgrade")        
        settings.XFORMS_DATABASE_ENGINE=settings.DATABASE_ENGINE
        settings.XFORMS_DATABASE_OPTIONS = settings.DATABASE_OPTIONS        
    

def _is_configured(config_func):
    from django.conf import settings
    #dmyung hack:
    #for django 1.2 compatability need to verify the db type for the default DB
    #and have xformmanager assume that it is that way.
    if not hasattr(settings, 'XFORMS_DATABASE_ENGINE'):
        _setup_xform_settings(settings)    
    return config_func(settings.XFORMS_DATABASE_ENGINE)    

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
    
