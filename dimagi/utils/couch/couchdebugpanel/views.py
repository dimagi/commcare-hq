"""
Author: Dan Myung dmyung@dimagi.com

This is heavily adapted from the views.py from the django_debug toolbar, specifically the sql debug panel.

Helper views for the debug toolbar. These are dynamically installed when the
debug toolbar is displayed, and typically can do Bad Things, so hooking up these
views in any other way is generally not advised.
"""

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.utils import simplejson
from django.utils.hashcompat import sha_constructor
from dimagi.utils.couch.database import get_db


class InvalidCouchQueryError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def couch_select(request):
    """
    Returns the output of the SQL SELECT statement.

    Expected GET variables:
        sql: urlencoded sql with positional arguments
        params: JSON encoded parameter values
        duration: time for SQL to execute passed in from toolbar just for redisplay
        hash: the hash of (secret + sql + params) for tamper checking
    """
    view_path_raw = request.GET.get('viewpath', '').replace('|','/')
    params = str(request.GET.get('params', ''))



    hash = sha_constructor(settings.SECRET_KEY + params + view_path_raw).hexdigest()
    view_path_arr = view_path_raw.split('/')
    view_path_arr.pop(0) #pop out the leading _design
    view_path_arr.pop(1) #pop out the middle _view
    view_path = '/'.join(view_path_arr)


    if hash != request.GET.get('hash', ''):
        return HttpResponseBadRequest('Tamper alert') # SQL Tampering alert
    db = get_db()
    params = params.replace("'",'"').replace("None", 'null').replace('True', 'true')
    print params
    params = simplejson.loads(params) #simplejson requires doublequotes for keys, nasty, None is not parseable by simplejson, converting to null

    kp = {}
    for k in params.keys():
        kp[str(k)] = params[k]

    json_raw = db.view(view_path, **kp).all()
    result = []
    for r in json_raw:
        result.append(simplejson.dumps(r, indent=4))


    context = {
        'view_name':view_path,
        'result': result,
        'params': params,
        'duration': request.GET.get('duration', 0.0),
    }
    return render_to_response('couchdebugpanel/couch_select.html', context)
