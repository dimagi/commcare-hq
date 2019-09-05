from jsonobject.properties import StringProperty

DATA_TYPE_DATE = 'date'
DATA_TYPE_DATETIME = 'datetime'
DATA_TYPE_STRING = 'string'
DATA_TYPE_INTEGER = 'integer'
DATA_TYPE_DECIMAL = 'decimal'
DATA_TYPE_ARRAY = 'array'
DATA_TYPE_BOOLEAN = 'boolean'  # note: should this be in DATA_TYPE_CHOICES?
DATA_TYPE_SMALL_INTEGER = 'small_integer'
DATA_TYPE_CHOICES = [
    DATA_TYPE_DATE,
    DATA_TYPE_DATETIME,
    DATA_TYPE_STRING,
    DATA_TYPE_INTEGER,
    DATA_TYPE_DECIMAL,
    DATA_TYPE_ARRAY,
    DATA_TYPE_SMALL_INTEGER,
]
NUMERIC_TYPE_CHOICES = (
    DATA_TYPE_INTEGER,
    DATA_TYPE_DECIMAL,
    DATA_TYPE_SMALL_INTEGER,
)


def DataTypeProperty(**kwargs):
    """
    Shortcut for valid data types.
    """
    return StringProperty(choices=DATA_TYPE_CHOICES, **kwargs)
