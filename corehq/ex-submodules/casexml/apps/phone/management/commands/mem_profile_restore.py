from optparse import make_option
from django.core.management import BaseCommand
from corehq.apps.users.models import CommCareUser
from casexml.apps.phone.restore import RestoreParams, RestoreCacheSettings, RestoreConfig
from casexml.apps.case.xml import V2
import resource


class Command(BaseCommand):
    """Prints out the memory allocated to this thread before and after a restore
    operation. Used to debug:
    http://manage.dimagi.com/default.asp?223540#1142280 and
    http://manage.dimagi.com/default.asp?225944#1142206

    Usage: ./manage.py mem_profile_restore --username large_caseload@domain.commcarehq.org
    """
    option_list = BaseCommand.option_list + (
        make_option('--username', action='store', dest='username'),
    )

    def handle(self, *args, **options):
        username = options['username']
        if not username:
            print "You need a username!"
            print "Usage: ./manage.py mem_profile_restore --username large_caseload@domain.commcarehq.org"
            return

        couch_user = CommCareUser.get_by_username(username)
        project = couch_user.project

        restore_config = RestoreConfig(
            project=project,
            user=couch_user.to_casexml_user(),
            params=RestoreParams(
                version=V2,
                include_item_count=True,
            ),
            cache_settings=RestoreCacheSettings(
                force_cache=True,
                cache_timeout=1,
                overwrite_cache=False,
            )
        )
        print 'Memory usage: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        restore_config.get_payload()
        print 'Memory usage: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
