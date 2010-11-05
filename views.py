from datetime import datetime, date, timedelta
from bhoma.utils.render_to_response import render_to_response
from django.http import HttpResponse
from bhoma.utils.couch.database import get_db
import logging

def device_list(db):
    assert False, str(list(db.view('phonelog/device_log_first_last', group=True)))

def devices(request):
    x = device_list(get_db())


    return render_to_response(request, 'phonelog/devicelist.html', {})
