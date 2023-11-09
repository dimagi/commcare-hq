import random
import time
from collections import namedtuple

from django.http import JsonResponse
from django.shortcuts import render

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
