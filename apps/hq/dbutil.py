from django.db import connection

def get_column_names(cursor):
    '''Get all column names from a cursor object
       (not including repeats)'''
    return [col[0] for col in cursor.description]

def get_column_names_from_table(table_name):
    '''Get all column names from a table.'''
    cursor = connection.cursor()
    # TODO: watch out for sql injection here!
    cursor.execute("describe %s" % table_name)
    return [col[0] for col in cursor.fetchall()]


def get_column_types_from_table(table_name):
    '''Get all column data types from a table.'''
    cursor = connection.cursor()
    # TODO: watch out for sql injection here!
    cursor.execute("describe %s" % table_name)
    return [col[1] for col in cursor.fetchall()]


