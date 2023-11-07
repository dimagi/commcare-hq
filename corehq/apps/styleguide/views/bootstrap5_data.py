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
