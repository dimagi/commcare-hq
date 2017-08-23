import csv
from optparse import make_option

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from corehq.apps.users.models import WebUser
from dimagi.utils.couch.database import iter_docs

from auditcare.models import NavigationEventAudit


def navigation_event_ids_by_user(user):
    database = NavigationEventAudit.get_db()

    return {row['id'] for row in database.view('auditcare/urlpath_by_user_date',
        startkey=[user ],
        endkey=[user, {}],
        reduce=False,
        include_docs=False,
    )}

def request_was_made_to_domain(domain, request_path):
    return request_path.startswith('/a/' + domain + '/')

def log_events(writer, domain, user, override_user=""):
    for event in iter_docs(NavigationEventAudit.get_db(), navigation_event_ids_by_user(user)):
        doc = NavigationEventAudit.wrap(event)
        if request_was_made_to_domain(domain, doc.request_path):
            log_event(writer, doc, override_user)

def log_event(writer, event, override_user=""):
    if override_user:
        event.user = override_user
    writer.writerow([event.user, event.event_date, event.ip_address, event.request_path])


class Command(BaseCommand):
    help = """Generate request report"""

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('filename')
        parser.add_argument(
            '--display-superuser',
            action='store_true',
            dest='display_superuser',
            default=False,
            help="Include superusers in report, otherwise 'Dimagi User'",
        )

    def handle(self, domain, filename, **options):
        display_superuser = options["display_superuser"]
        dimagi_username = ""

        if not display_superuser:
            dimagi_username = "Dimagi Support"

        users = {u.username for u in WebUser.by_domain(domain)}
        super_users = {u['username'] for u in User.objects.filter(is_superuser=True).values('username')}
        super_users = super_users - users

        with open(filename, 'wb') as csvfile:
            writer = csv.writer(csvfile)
            for user in users:
                log_events(writer, domain, user)

            for user in super_users:
                log_events(writer, domain, user, dimagi_username)
