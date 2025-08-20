from django.db import models


class MakeInterval(models.Func):
    """Django Func class for the 'make_interval' database function
    See https://www.postgresql.org/docs/15/functions-datetime.html
    """
    function = "make_interval"
    arity = 2
    arg_joiner = "=>"

    def __init__(self, unit, value):
        assert unit in ("years", "months", "days", "hours", "mins", "secs")
        expressions = (UnquotedValue(unit), value)
        super().__init__(*expressions, output_field=models.DateTimeField())


class UnquotedValue(models.Value):
    """Raw value with no formatting (not even quotes).
    This used for database keywords."""
    def as_sql(self, compiler, connection):
        return self.value, []
