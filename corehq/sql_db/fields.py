import sys

from django.db.models import CharField


class CharIdField(CharField):
    """CharField that does not create varchar_pattern_ops index

    Django automatically creates varchar_pattern_ops indexes for indexed
    varchar columns to support `LIKE` and regular expression queries. ID
    fields are not typically quieried with those operators, and
    therefore the extra index would degrade performance and consume
    storage for no benefit.
    """

    def db_type(self, connection):
        # HACK short circuit index creation based on caller name
        if _get_caller_name() == "_create_like_index_sql":
            return None
        return super().db_type(connection)


def _get_caller_name():
    return sys._getframe(2).f_code.co_name
