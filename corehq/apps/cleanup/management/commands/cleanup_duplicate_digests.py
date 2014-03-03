import csv
from optparse import make_option
from django.core.management.base import BaseCommand
from django_digest.models import PartialDigest
from dimagi.utils.decorators.log_exception import log_exception


class Command(BaseCommand):
    """
    Cleans up duplicate partial digests in the system.
    """
    option_list = BaseCommand.option_list + (
        make_option('--cleanup',
                    action='store_true',
                    dest='cleanup',
                    default=False,
                    help="Clean up (delete) the affected cases."),
    )

    @log_exception()
    def handle(self, *args, **options):
        with open('duplicate-digests.csv', 'wb') as f:
            writer = csv.writer(f, dialect=csv.excel)
            # headings
            writer.writerow([
                'user id',
                'username',
                'email',
                'digest id',
                'login',
            ])
            for digest in PartialDigest.objects.all():
                if digest.user.username.lower() != digest.login.lower():
                    writer.writerow([
                        digest.user.pk,
                        digest.user.username,
                        digest.user.email,
                        digest.pk,
                        digest.login,
                    ])
                    if options['cleanup']:
                        digest.delete()
