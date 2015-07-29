import datetime


ASCENDING = "ASC"
DESCENDING = "DESC"


def get_default_sort_value(datatype, order):
    """
    Gets a default sort value based on a datatype and order

    order must be one of ASCENDING or DESCENDING fro mreports
    """
    defaults = {
        "date": {
            ASCENDING: datetime.date.max,
            DESCENDING: datetime.date.min,
        },
        "datetime": {
            ASCENDING: datetime.datetime.max,
            DESCENDING: datetime.datetime.min,
        },
    }
    global_defaults = {
        ASCENDING: None,
        DESCENDING: None
    }
    return defaults.get(datatype, global_defaults)[order]
