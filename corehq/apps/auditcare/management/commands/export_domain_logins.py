import argparse
import csv
import gzip
from contextlib import contextmanager
from textwrap import dedent

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.auditcare.utils.export import get_domain_first_access_times
from corehq.apps.domain.models import Domain
from corehq.util.argparse_types import date_type


class Command(BaseCommand):

    help = dedent("""\
        Generate request report of domain "login" events.

        NOTES
            - Queries SQL `NavigationEventAudit` events for "domain login times".
            - See `export.get_domain_first_access_times()` for more details.
            - Does _not_ query couch!
    """)

    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        # adding `formatter_class` to kwargs causes BaseCommand to specify it twice
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument("-o", "--outfile", metavar="FILE",
            help="write output to %(metavar)s rather than STDOUT")
        parser.add_argument("-z", "--gzip", action="store_true", default=False,
            help="gzip-compress the output (only valid with --outfile option)")
        parser.add_argument("-s", "--start", metavar="YYYY-MM-DD", type=date_type,
            help="query login events starting %(metavar)s")
        parser.add_argument("-e", "--end", metavar="YYYY-MM-DD", type=date_type,
            help="query login events ending %(metavar)s")
        parser.add_argument("domains", metavar="DOMAIN", nargs="+",
            help="query login events for %(metavar)s(s)")

    def handle(self, **options):
        outfile = options["outfile"]
        if outfile is None:
            outfile = self.stdout

            @contextmanager
            def opener(file, mode):
                yield file

            if options["gzip"]:
                raise CommandError("--gzip option requires specifying --outfile")
        else:
            if options["gzip"]:
                opener = gzip.open
            else:
                opener = open

        domains = self.validate_domains(options["domains"])
        with opener(outfile, "wt") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Date", "Domain", "Username"])
            for event in get_domain_first_access_times(domains, options["start"],
                                                       options["end"]):
                writer.writerow([
                    event["access_time"],
                    event["domain"],
                    event["user"],
                ])

    @staticmethod
    def validate_domains(domains):
        for domain in domains:
            if not Domain.get_by_name(domain):
                raise CommandError(f"Invalid domain name: {domain}")
        return domains
