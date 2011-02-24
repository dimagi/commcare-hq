
def get_unique_value(query_set, field_name, value, sep="_", suffix=""):

    """Gets a unique name for an object corresponding to a particular
       django query.  Useful if you've defined your field as unique
       but are system-generating the values.  Starts by checking
       <value> and then goes to <value>_2, <value>_3, ... until 
       it finds the first unique entry. Assumes <value> is a string"""
    
    def format(pref, suf):
        return "%s%s" % (pref, suf)
    original_prefix = value
    value = format(value, suffix)
    column_count = query_set.filter(**{field_name: value}).count()
    to_append = 2
    while column_count != 0:
        new_prefix = "%s%s%s" % (original_prefix, sep, to_append)
        value = format(new_prefix, suffix)
        column_count = query_set.filter(**{field_name: value}).count()
        to_append = to_append + 1
    return value
                    

