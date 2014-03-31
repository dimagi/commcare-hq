import json
import datetime
from django.utils.encoding import force_unicode
from django.utils.functional import Promise


class LazyEncoder(json.JSONEncoder):
    """Taken from https://github.com/tomchristie/django-rest-framework/issues/87
    This makes sure that ugettext_lazy refrences in a dict are properly evaluated
    """
    def default(self, obj):
        if isinstance(obj, Promise):
            return force_unicode(obj)
        return super(LazyEncoder, self).default(obj)
