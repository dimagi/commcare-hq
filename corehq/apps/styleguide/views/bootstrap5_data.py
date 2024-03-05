import random
import time
from collections import namedtuple
from gettext import gettext

from django.http import JsonResponse
from django.shortcuts import render

from corehq.apps.styleguide.utils import get_fake_tabular_data

FakeUser = namedtuple('FakeUser', 'id username')


def select2_ajax_demo(request):
    request_data = request.POST if request.method == 'POST' else request.GET
    users = [
        FakeUser('12345', 'fisconsp'),
        FakeUser('23523', 'acesureq'),
        FakeUser('234235', 'ivendial'),
        FakeUser('2352352', 'letricav'),
        FakeUser('54645623', 'viogrelo'),
        FakeUser('346233456', 'maravegran'),
        FakeUser('3242314', 'eruseheram'),
        FakeUser('7897543', 'ordistager'),
        FakeUser('54678', 'itecusepec'),
    ]

    page = int(request_data.get('page', 1))
    size = int(request_data.get('page_limit', 5))
    start = size * (page - 1)
    query = request_data.get('q', '')

    filtered_users = [u for u in users if query in u.username] if query else users
    total = len(filtered_users)
    end = min(size * page, total)
    filtered_users = filtered_users[start:end]
    results = [
        {'id': u.id, 'text': u.username} for u in filtered_users
    ]

    return JsonResponse({
        "results": results,
        "total": total,
    })


def remote_modal_demo(request):
    secret_message = request.GET.get('testParam')
    return render(request, "styleguide/bootstrap5/examples/remote_modal.html", {
        "secret_message": secret_message,
    })


def inline_edit_demo(request):
    time.sleep(1)  # simulates a long process, so we can preview / check spinner icon
    show_error = random.randint(0, 1)
    if show_error:
        response = JsonResponse({
            "error": "This is a random error returned from the server. Try again until it succeeds.",
        })
        response.status_code = 400
        return response

    return JsonResponse({
        "do_something_with_this": {
            "secret_message": "hi",
        },
        "posted_data": request.POST,
    })


def submit_feedback_demo(request):
    """See domain.views.feedback.submit_feedback for ow this is actually used"""
    return JsonResponse({
        "success": True,
    })


def validate_ko_demo(request):
    time.sleep(1)  # simulates a long process, so we can preview / check spinner icon
    response = {
        "isValid": True,
    }
    if request.POST.get('username') == 'jon':
        response = {
            "isValid": False,
            "message": gettext("This username is already taken. Please try another one."),
        }
    if request.POST.get('email') == 'jon@dimagi.com':
        response = {
            "isValid": False,
            "message": gettext("This email is already assigned to a user. Please use another email."),
        }
    return JsonResponse(response)


def datatables_data(request):
    return JsonResponse({
        "data": get_fake_tabular_data(50),
    })


def paginated_table_data(request):
    page = int(request.POST.get('page'))
    limit = int(request.POST.get('limit'))
    start = (page - 1) * limit
    fake_data = get_fake_tabular_data(100)
    total = len(fake_data)
    end = min(page * limit, total)
    return JsonResponse({
        "total": len(fake_data),
        "rows": fake_data[start:end],
    })
