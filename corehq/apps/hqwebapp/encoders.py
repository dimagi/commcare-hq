import json
from decimal import Decimal

from django.utils.encoding import force_str
from django.utils.functional import Promise


class DecimalEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)


class LazyEncoder(DecimalEncoder):
    """Taken from https://github.com/tomchristie/django-rest-framework/issues/87
    This makes sure that gettext_lazy refrences in a dict are properly evaluated
    """

    def default(self, obj):
        if isinstance(obj, Promise):
            return force_str(obj)
        return super(LazyEncoder, self).default(obj)
