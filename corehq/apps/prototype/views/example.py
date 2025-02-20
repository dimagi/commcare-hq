import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from corehq import toggles
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.prototype.utils import fake_data
from corehq.util.quickcache import quickcache


@login_required
@use_bootstrap5
@toggles.SAAS_PROTOTYPE.required_decorator()
def knockout_pagination(request):
    return render(request, 'prototype/example/knockout_pagination.html', {})


@quickcache(['num_entries'])
def _generate_example_paginated_data(num_entries):
    rows = []
    for row in range(0, num_entries):
        rows.append([
            f"{fake_data.get_first_name()} {fake_data.get_last_name()}",
            fake_data.get_color(),
            fake_data.get_big_cat(),
            fake_data.get_planet(),
            fake_data.get_fake_app(),
            fake_data.get_past_date(),
        ])
    return rows


@login_required
@require_POST
@toggles.SAAS_PROTOTYPE.required_decorator()
def example_paginated_data(request):
    page = int(request.POST.get('page'))
    limit = int(request.POST.get('limit'))

    data = _generate_example_paginated_data(100)

    start = (page - 1) * limit
    total = len(data)
    end = min(page * limit, total)

    rows = data[start:end]
    return JsonResponse({
        "total": len(data),
        "rows": rows,
    })


def generate_ics(request):
    now = datetime.datetime.now()
    dtstart = now.strftime('%Y%m%dT%H%M%S')
    dtend = (now + datetime.timedelta(hours=1)).strftime('%Y%m%dT%H%M%S')

    ics_content = f"""
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Your Organisation//Example Project//EN
BEGIN:VEVENT
UID:1
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY: Event for Today
LOCATION:
END:VEVENT
END:VCALENDAR
"""

    response = HttpResponse(ics_content, content_type='text/calendar')
    response['Content-Disposition'] = 'attachment; filename=event.ics'

    return response
