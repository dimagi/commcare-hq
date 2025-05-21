from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.domain_migration_flags.api import (
    get_migration_complete,
    set_migration_complete,
    set_migration_started,
)
from corehq.apps.users.models import CommCareUser
from corehq.dbaccessors.couchapps.all_docs import (
    get_doc_count_by_domain_type,
    paginate_view,
)
from corehq.util.couch import DocUpdate, IterUpdateError, iter_update
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = 'Fix truncated commcare_version for mobile users'

    def handle(self, *args, **kwargs):
        db = CommCareUser.get_db()
        domain_names = Domain.get_all_names()

        for domain in domain_names:
            if get_migration_complete(domain, 'fix_commcare_version'):
                continue
            count = get_doc_count_by_domain_type(db, domain, 'CommCareUser')
            all_ids = (row['id'] for row in paginate_view(
                db,
                'by_domain_doc_type_date/view',
                chunk_size=10000,
                startkey=[domain, 'CommCareUser'],
                endkey=[domain, 'CommCareUser', {}],
                include_docs=False,
                reduce=False,
            ))
            set_migration_started(domain, 'fix_commcare_version')
            try:
                res = iter_update(db, update_commcare_version, with_progress_bar(all_ids, count))
            except IterUpdateError:
                print(f"Error updating commcare_version for domain {domain}")
                print(res.error_ids)
                continue
            set_migration_complete(domain, 'fix_commcare_version')


def update_commcare_version(user_doc):
    changes_made = False
    try:
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
    except Exception:
        # Return something else other than None or DocUpdate to indicate an error
        return Exception
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
