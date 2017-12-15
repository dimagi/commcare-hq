"""
Person and Voucher cases use a custom ID generation scheme for shorter,
readable IDs. There have been errors in this scheme resulting in duplicate IDs.
This file is a collection of utilities around identifying such cases, figuring
out the cause of the duplication, and resolving duplicates.
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from collections import Counter
import six

from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CaseTransaction
from dimagi.utils.couch.database import iter_docs

from .const import VOUCHER_ID, ENIKSHAY_ID
from .models import IssuerId
from .user_setup import compress_nikshay_id


def get_cases_with_duplicate_ids(domain, case_type):
    accessor = CaseAccessors(domain)
    id_property = {'voucher': VOUCHER_ID, 'person': ENIKSHAY_ID}[case_type]
    all_case_ids = accessor.get_case_ids_in_domain(case_type)
    all_cases = [
        {
            'case_id': case.case_id,
            'readable_id': case.get_case_property(id_property),
            'opened_on': case.opened_on,
        }
        for case in accessor.iter_cases(all_case_ids)
    ]
    counts = Counter(case['readable_id'] for case in all_cases)
    bad_cases = (case for case in all_cases if counts[case['readable_id']] > 1)
    return sorted(bad_cases, key=lambda case: case['opened_on'], reverse=True)


def add_debug_info_to_cases(bad_cases, limit_debug_to):
    _add_form_info_to_cases(bad_cases, limit_debug_to)
    _add_user_info_to_cases(bad_cases)


def _add_form_info_to_cases(bad_cases, limit_debug_to):
    for case in bad_cases[:limit_debug_to]:
        form = CaseAccessorSQL.get_transactions_by_type(
            case['case_id'], CaseTransaction.TYPE_CASE_CREATE,
        )[0].form
        case['form_name'] = form.form_data.get('@name', 'NA')
        form_device_number = form.form_data.get('serial_id', {}).get('outputs', {}).get('device_number')
        case['device_number_in_form'] = form_device_number
        case['form_device_id'] = form.metadata.deviceID
        case['form_user_id'] = form.user_id
        case['auth_user_id'] = form.auth_context.get('user_id')


def _add_user_info_to_cases(bad_cases):
    user_info = _get_user_info(
        case['form_user_id'] for case in bad_cases if 'form_user_id' in case)

    auth_user_ids = [case['auth_user_id'] for case in bad_cases
                     if 'auth_user_id' in case]
    auth_usernames = {user_doc['_id']: user_doc['username'] for user_doc in
                      iter_docs(CommCareUser.get_db(), auth_user_ids)}
    for case in bad_cases:
        user_dict = user_info.get(case.get('form_user_id'))
        if user_dict:
            case['username'] = user_dict['username']
            device_id = case['form_device_id']
            if device_id == 'Formplayer':
                # Hazard a guess as to what device ID was used in the restore
                if case['form_user_id'] == case['auth_user_id']:
                    device_id = "WebAppsLogin"
                else:
                    auth_username = auth_usernames.get(case['auth_user_id'])
                    device_id = "WebAppsLogin*{}*as*{}".format(
                        auth_username, user_dict['username']).replace('.', '_')
            try:
                device_number = user_dict['device_ids'].index(device_id) + 1
            except ValueError:
                device_number = -1
            case['real_device_number'] = six.text_type(device_number)


def _get_user_info(user_ids):
    return {
        user_doc['_id']: {
            'username': user_doc['username'].split('@')[0],
            'device_ids': [d['device_id'] for d in user_doc['devices']],
        }
        for user_doc in iter_docs(CommCareUser.get_db(), user_ids)
    }


class ReadableIdGenerator(object):

    def __init__(self, domain, commit):
        self.domain = domain
        self.commit = commit
        self._issuer_id = -1
        self._device_number = 0
        self._serial_count = -1

    def _bump_issuer_id(self):
        if self.commit:
            issuer_id, _ = IssuerId.objects.get_or_create(domain=self.domain,
                                                          user_id="duplicate_generator")
            self._issuer_id = issuer_id.pk
        else:
            # this isn't going to be saved, just start at 0
            self._issuer_id += 1

    def _get_issuer_id(self):
        if self._issuer_id == -1:
            self._bump_issuer_id()
        return self._issuer_id

    def _get_device_number(self):
        if self._device_number == 10:
            self._bump_issuer_id()
            self._device_number = 0
        return self._device_number

    def _get_serial_count(self):
        self._serial_count += 1
        if self._serial_count == 5000:
            self._serial_count = 0
            self._device_number += 1
        return self._serial_count

    def get_next(self):
        # order matters, since more specific ones roll up the next
        serial_count = self._get_serial_count()
        device_number = self._get_device_number()
        issuer_id = self._get_issuer_id()
        return "{}{}{}".format(
            compress_nikshay_id(issuer_id, 3),
            compress_nikshay_id(device_number, 0),
            compress_nikshay_id(serial_count, 2),
        )
