from django.core.management.base import BaseCommand
from corehq.apps.users.dbaccessors import get_all_user_rows, get_mobile_user_count
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.util.log import with_progress_bar
from corehq.apps.es import DomainES, filters


class Command(BaseCommand):
    help = 'Fix truncated commcare_version for mobile users'

    def handle(self, *args, **kwargs):
        self.update_commcare_version()

    def update_commcare_version(self):
        total_update = 0
        total_users = 0
        is_domain_active = filters.term('is_active', True)
        active_domains = (
            DomainES().filter(is_domain_active)
            .terms_aggregation('name.exact', 'domain')
            .size(0).run().aggregations.domain.keys
        )

        for domain in with_progress_bar(active_domains, len(active_domains)):
            total_users_in_domain = get_mobile_user_count(domain)
            total_users += total_users_in_domain
            users = get_all_user_rows(domain, include_web_users=False, include_mobile_users=True,
                                      include_inactive=True, include_docs=True)

            for user in users:
                user = CouchUser.wrap_correctly(user['doc'])

                changes_made = False
                if getattr(user, 'devices', None):
                    changes_made |= self.update_version(user.last_device, 'commcare_version')
                    for device in user.devices:
                        changes_made |= self.update_version(device, 'commcare_version')
                if getattr(user.reporting_metadata, 'submissions', None):
                    changes_made |= self.update_version(user.reporting_metadata.last_submission_for_user,
                                                        'commcare_version')
                    for submission in user.reporting_metadata.submissions:
                        changes_made |= self.update_version(submission, 'commcare_version')
                if changes_made:
                    CommCareUser.save_docs([user])
                    total_update += 1
        print(f"Updated {total_update} users out of {total_users}")

    def update_version(self, obj, attr_name):
        original_version = getattr(obj, attr_name, None)
        new_version = self._fix_commcare_version(original_version)
        if new_version != original_version:
            setattr(obj, attr_name, new_version)
            return True
        return False

    def _fix_commcare_version(self, version):
        if version and version.count('.') == 1:
            return f"{version}.0"
        elif version and version.count('.') == 0:
            return f"{version}.0.0"
        else:
            return version
