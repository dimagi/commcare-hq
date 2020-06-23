from datetime import datetime, time
from functools import wraps

from django.http import Http404
from django.utils.translation import ugettext as _

from couchdbkit import ResourceNotFound
from django_prbac.utils import has_privilege

from corehq import privileges, toggles
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_brief_apps_in_domain,
)
from corehq.apps.app_manager.util import is_remote_app
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.mixin import (
    CommCareMobileContactMixin,
    InvalidFormatException,
    apply_leniency,
)
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.form_processor.utils import is_commcarecase
from corehq.util.quickcache import quickcache


# Several SMS forms collect app id and form unique id in a single input
def get_combined_id(app_id, form_unique_id):
    if app_id is None and form_unique_id is None:
        return None

    app_id = app_id or ''
    form_unique_id = form_unique_id or ''

    if '|' in app_id:
        raise ValueError("Unexpected token '|' in app_id '%s'" % app_id)

    if '|' in form_unique_id:
        raise ValueError("Unexpected token '|' in form_unique_id '%s'" % form_unique_id)

    return '%s|%s' % (app_id, form_unique_id)


def split_combined_id(combined_id):
    if combined_id is None:
        return None, None

    if '|' not in combined_id:
        raise ValueError("Combined id badly formatted")

    return combined_id.split('|')


class DotExpandedDict(dict):
    """

    A special dictionary constructor that takes a dictionary in which the keys
    may contain dots to specify inner dictionaries. It's confusing, but this
    example should make sense.

    Taken from last version of the class, removed in Django 1.5
    https://github.com/django/django/blob/0f57935bcd8cd525d8d661c5af4fb70b79e126ae/django/utils/datastructures.py

    >>> d = DotExpandedDict({'person.1.firstname': ['Simon'], \
            'person.1.lastname': ['Willison'], \
            'person.2.firstname': ['Adrian'], \
            'person.2.lastname': ['Holovaty']})
    >>> d
    {'person': {'1': {'lastname': ['Willison'], 'firstname': ['Simon']}, '2': {'lastname': ['Holovaty'], 'firstname': ['Adrian']}}}
    >>> d['person']
    {'1': {'lastname': ['Willison'], 'firstname': ['Simon']}, '2': {'lastname': ['Holovaty'], 'firstname': ['Adrian']}}
    >>> d['person']['1']
    {'lastname': ['Willison'], 'firstname': ['Simon']}

    # Gotcha: Results are unpredictable if the dots are "uneven":
    >>> DotExpandedDict({'c.1': 2, 'c.2': 3, 'c': 1})
    {'c': 1}
    """

    def __init__(self, key_to_list_mapping):
        for k, v in key_to_list_mapping.items():
            current = self
            bits = k.split('.')
            for bit in bits[:-1]:
                current = current.setdefault(bit, {})
            # Now assign value to current position
            try:
                current[bits[-1]] = v
            except TypeError: # Special-case if current isn't a dict.
                current = {bits[-1]: v}


def get_form_list(domain):
    form_list = []
    briefs = get_brief_apps_in_domain(domain)
    for brief in sorted(briefs, key=lambda b: b.name):
        latest_app = get_app(domain, brief.id, latest=True)
        if not is_remote_app(latest_app):
            for m in latest_app.get_modules():
                for f in m.get_forms():
                    form_list.append({
                        "code": get_combined_id(latest_app.master_id, f.unique_id),
                        "name": f.full_path_name,
                    })
    return form_list


def get_two_way_number_for_recipient(recipient):
    if isinstance(recipient, CommCareMobileContactMixin):
        two_way_numbers = recipient.get_two_way_numbers()
        if len(two_way_numbers) == 1:
            return list(two_way_numbers.values())[0]
        elif len(two_way_numbers) > 1:
            # Retrieve the two-way number that's highest up in the list
            if isinstance(recipient, CouchUser):
                for phone in recipient.phone_numbers:
                    if phone in two_way_numbers:
                        return two_way_numbers[phone]
                raise Exception("Phone number list and PhoneNumber entries are out "
                                "of sync for user %s" % recipient.get_id)
            else:
                raise Exception("Expected a CouchUser")
    return None


def get_one_way_number_for_recipient(recipient):
    if isinstance(recipient, CouchUser):
        return recipient.phone_number
    elif is_commcarecase(recipient):
        one_way_number = recipient.get_case_property('contact_phone_number')
        one_way_number = apply_leniency(one_way_number)
        if one_way_number:
            try:
                CommCareMobileContactMixin.validate_number_format(one_way_number)
                return one_way_number
            except InvalidFormatException:
                return None
    return None
