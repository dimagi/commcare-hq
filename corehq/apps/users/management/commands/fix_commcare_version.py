from itertools import chain

from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser
from corehq.dbaccessors.couchapps.all_docs import (
    get_doc_count_by_type,
    iter_all_doc_ids,
)
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = 'Fix truncated commcare_version for mobile users'

    def handle(self, *args, **kwargs):
        db = CommCareUser.get_db()
        count = get_doc_count_by_type(db, 'CommCareUser')
        all_ids = chain(iter_all_doc_ids(db, 'CommCareUser'))
        iter_update(db, update_commcare_version, with_progress_bar(all_ids, count), verbose=True)


def update_commcare_version(user_doc):
    changes_made = False
    if 'devices' in user_doc and user_doc['devices']:
        if 'last_device' in user_doc:
            changes_made = update_version(user_doc['last_device'], 'commcare_version')
        for device in user_doc['devices']:
            changes_made |= update_version(device, 'commcare_version')
    if ('reporting_metadata' in user_doc
            and 'last_submissions' in user_doc['reporting_metadata']
            and user_doc['reporting_metadata']['last_submissions']):
        if 'last_submission_for_user' in user_doc['reporting_metadata']:
            changes_made |= update_version(
                user_doc['reporting_metadata']['last_submission_for_user'],
                'commcare_version'
            )
        for submission in user_doc['reporting_metadata']['last_submissions']:
            changes_made |= update_version(submission, 'commcare_version')
    if changes_made:
        return DocUpdate(user_doc)
    else:
        return None


def update_version(obj, attr_name):
    original_version = obj.get(attr_name)
    new_version = _fix_commcare_version(original_version)
    if new_version != original_version:
        obj[attr_name] = new_version
        return True
    return False


def _fix_commcare_version(version):
    if version and version.count('.') == 1:
        return f"{version}.0"
    elif version and version.count('.') == 0:
        return f"{version}.0.0"
    else:
        return version
