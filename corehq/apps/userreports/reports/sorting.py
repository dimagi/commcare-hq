import datetime


ASCENDING = "ASC"
DESCENDING = "DESC"


def get_default_sort_value(datatype):
    """
    Gets a default sort value based on a datatype and order for null values.

    Generally tries to return the first possible value
    """
    defaults = {
        'date': datetime.date.min,
        'datetime': datetime.datetime.min,
        'string': ''
    }
    return defaults.get(datatype, None)
