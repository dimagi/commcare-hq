

def get_column_names(cursor):
    '''Get all column names from a cursor object
       (not including repeats)'''
    return [col[0] for col in cursor.description]


