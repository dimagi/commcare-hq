
def get_unique_value(query_set, field_name, value, sep=""):

    """Gets a unique name for an object corresponding to a particular
       django query.  Useful if you've defined your field as unique
       but are system-generating the values.  Starts by checking
       <value> and then goes to <value>_2, <value>_3, ... until 
       it finds the first unique entry. Assumes <value> is a string"""
    
    original_value = value
    column_count = query_set.filter(**{field_name: value}).count()
    to_append = 1
    while column_count != 0:
        value = "%s%s%s" % (original_value, sep, to_append)
        column_count = query_set.filter(**{field_name: value}).count()
        to_append = to_append + 1
    return value
