import datetime
import json
import random
from collections import namedtuple

from django.http import JsonResponse
from django.shortcuts import render
from django.core.cache import cache

from corehq import toggles
from corehq.apps.accounting.utils import months_from_date
from corehq.apps.hqwebapp.decorators import use_bootstrap5

FakeData = namedtuple('FakeData', 'slug value')
FAKE_USER = 'testuser@dimagi.com'


@use_bootstrap5
def clean_data_prototype(request):
    return render(request, 'styleguide/sketch/clean_data.html', {})


def get_data_for_data_cleaning_prototype(request):
    page = int(request.POST.get('page'))
    limit = int(request.POST.get('limit'))

    data = get_test_data_for_request(request)

    start = (page - 1) * limit
    total = len(data)
    end = min(page * limit, total)

    rows = data[start:end]
    return JsonResponse({
        "total": len(data),
        "rows": rows,
    })


def get_all_data_for_data_cleaning_prototype(request):
    data = get_test_data_for_request(request)
    return JsonResponse({
        "rows": data,
    })


def update_sprint_data(request):
    old_data = get_test_data_for_request(request)
    new_data = json.loads(request.POST.get('rows'))
    return JsonResponse({
        "success": True,
    })
    if update_all:
        update_test_data_for_request(request, new_data)
        return JsonResponse({
            "success": "Updated all records",
        })

    page = int(request.POST.get('page'))
    limit = int(request.POST.get('limit'))

    start = (page - 1) * limit
    total = len(old_data)
    end = min(page * limit, total)

    old_data[start:end] = new_data
    update_test_data_for_request(request, old_data)
    return JsonResponse({
        "success": f"Updated {len(old_data)} record(s).",
    })


@toggles.SAAS_DESIGN_SPRINT.required_decorator()
def clear_cached_sprint_data(request):
    # cache.delete(_get_cache_key(request.user.username))
    cache.delete(_get_cache_key(FAKE_USER))
    return JsonResponse({
        "success": True,
    })


def _get_cache_key(username):
    return f"{username}:saas-design-sprint-prototype"


def update_test_data_for_request(request, data):
    cache.set(_get_cache_key(FAKE_USER), data, 24 * 60 * 60)


def get_test_data_for_request(request):
    data = cache.get(_get_cache_key(FAKE_USER))
    if not data:
        data = get_fake_tabular_data_with_issues(200)
        update_test_data_for_request(request, data)
    return data


def get_fake_tabular_data_with_issues(num_entries):
    status = ('open', 'closed')
    apps = ('MCH V2', 'MCH V1', 'MCH V5')
    today = datetime.datetime.today()
    submitted_on = months_from_date(today, -1 * random.choice([0, 1, 2, 3])).strftime("%Y-%m-%d")
    rows = []
    for row_id in range(0, num_entries):
        rows.append({
            'id': row_id,
            'data': [
                FakeData('full_name', get_full_name())._asdict(),
                FakeData('color', get_color())._asdict(),
                FakeData('big_cat', get_big_cat())._asdict(),
                FakeData('submitted_on', submitted_on)._asdict(),
                FakeData('app', random.choice(apps))._asdict(),
                FakeData('status', random.choice(status))._asdict(),
            ],
        })
    return rows


def _append_checkbox(row):
    return ['#ko-check-template'] + row


def get_text_value_with_issues(value, can_be_missing=False):
    is_missing = bool(random.getrandbits(1))
    if is_missing and can_be_missing:
        return ""

    num_whitespace = random.choice([0, 1, 2, 4])
    value = '&nbsp;' * num_whitespace + value
    return value


def get_full_name():
    return get_first_name() + " " + get_last_name()


def get_big_cat():
    big_cats = ('cheetah', 'lion', 'tiger', 'panther')
    return get_text_value_with_issues(random.choice(big_cats), can_be_missing=True)


def get_color():
    colors = ('blue', 'green', 'red', 'purple', 'salmon')
    return get_text_value_with_issues(random.choice(colors), can_be_missing=True)


def get_first_name():
    first_names = (
        'Arundhati', 'Karan', 'Salman', 'Aravind', 'Katherine', 'Ethan', 'Luna', 'Olivia', 'Stella', 'Aiden',
        'Santiago', 'Sophia', 'Parry', 'Vahan', 'Vaishnavi', 'Wambui', 'Trish', 'Prakash',
    )
    return get_text_value_with_issues(random.choice(first_names))


def get_last_name():
    first_names = (
        'Rosalynne', 'Edwena', 'Karla', 'Zak', 'Eddy', 'Meg', 'Kelebogile', 'Monday', 'Coba', 'Zenzi', 'Rebecca',
        'Sindy', 'Earline', 'Joeri', 'Hartmann', 'Elicia', 'Marianna', 'Jonathon', 'Emilia', 'Srinivas',
    )
    return get_text_value_with_issues(random.choice(first_names))