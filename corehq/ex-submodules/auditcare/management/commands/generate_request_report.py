from __future__ import absolute_import
from __future__ import unicode_literals
import csv

from datetime import datetime

import argparse
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from auditcare.utils.export import write_log_events, get_users_to_export
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = """Generate request report"""

    def add_arguments(self, parser):
        parser.add_argument('filename', help="Output file path")
        parser.add_argument(
            '-d'
            '--domain',
            dest='domain',
            help="Limit logs to only this domain"
        )
        parser.add_argument(
            '-u',
            '--user',
            dest='user',
            help="Limit logs to only this user"
        )
        parser.add_argument(
            '-s',
            '--startdate',
            dest='start',
            type=valid_date,
            help="The start date - format YYYY-MM-DD",
        )
        parser.add_argument(
            '-e',
            '--enddate',
            dest='end',
            type=valid_date,
            help="The end date - format YYYY-MM-DD",
        )
        parser.add_argument(
            '--display-superuser',
            action='store_true',
            dest='display_superuser',
            default=False,
            help="Include superusers in report, otherwise 'Dimagi User'",
        )

    def handle(self, filename, **options):
        domain = options["domain"]
        user = options["user"]
        display_superuser = options["display_superuser"]

        dimagi_username = ""
        if not display_superuser:
            dimagi_username = "Dimagi Support"

        if not domain and not user:
            raise CommandError("Please provide one of 'domain' or 'user'")

        if domain:
            domain_object = Domain.get_by_name(domain)
            if not domain_object:
                raise CommandError("Domain not found")

        users, super_users = get_users_to_export(user, domain)

        with open(filename, 'wb') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Date', 'User', 'Domain', 'IP Address', 'Request Path'])
            for user in users:
                write_log_events(
                    writer, user, domain,
                    start_date=options['start'], end_date=options['end']
                )

            for user in super_users:
                write_log_events(
                    writer, user, domain,
                    override_user=dimagi_username,
                    start_date=options['start'], end_date=options['end']
                )
