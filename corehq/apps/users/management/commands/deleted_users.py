"""
List the IDs of deleted users for a given domain
"""

from django.core.management import BaseCommand

from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_class
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.users.dbaccessors.all_commcare_users import get_mobile_user_ids
from corehq.apps.users.models import CommCareUser


class Command(BaseCommand):
    help = __doc__.strip()  # (The module's docstring)

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--usernames',
            action='store_true',
            dest='with_usernames',
            default=False,
            help="Include usernames in the list of IDs",
        )

    def handle(self, domain, **options):
        mobile_users = get_mobile_user_ids(domain)
        everyone = set(get_doc_ids_in_domain_by_class(domain, CommCareUser))
        deleted = everyone - mobile_users
        # See also corehq.apps.dump_reload.management.commands.print_domain_stats._get_couchdb_counts

        id_ = None
        for id_ in deleted:
            if options['with_usernames']:
                doc_info = get_doc_info_by_id(domain, id_)
                print(id_, doc_info.display)
            else:
                print(id_)
        if id_ is None:
            print('Domain "{}" has no deleted users'.format(domain))
