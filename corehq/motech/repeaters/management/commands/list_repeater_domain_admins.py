import csv
import logging
from argparse import FileType

from django.core.management.base import BaseCommand
from corehq.apps.users.models import WebUser
from corehq.motech.repeaters.models import Repeater

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Shows names and admin emails of Domains with Repeaters."""

    def add_arguments(self, parser):
        parser.add_argument("--csv", action="store_true", default=False,
            help="Write output as CSV data instead of padded table.")
        parser.add_argument("-o", "--output", metavar="FILE", type=FileType("w"),
            default=self.stdout, help="Write output to %(metavar)s (default=STDOUT).")

    def handle(self, *args, **options):
        log.debug("fetching repeaters")
        table = Table(["Domain", "Admins"])
        for summary in Repeater.get_db().view('repeaters/repeaters',
                                              group_level=1, reduce=True).all():
            domain = summary["key"][0]
            log.debug("domain %s has %s repeater(s)", domain, summary['value'])
            emails = set()
            for admin in WebUser.get_admins_by_domain(domain):
                emails.add(admin.email if admin.email else admin.username)
            table.add_row([domain, ", ".join(sorted(emails))])
        table.sort()
        if options["csv"]:
            table.write_csv(options["output"])
        else:
            options["output"].write(table.render())


class Table:
    """Convenience class for rendering tables with space-padded columns."""

    JUST_MAP = dict(c="center", l="ljust", r="rjust")

    def __init__(self, header=None, max_col_width=24):
        self.header = header
        self.max_col_width = max_col_width
        self.rows = []
        self.widths = []
        if header is not None:
            self.add_row(header)

    def add_row(self, row):
        """Add a row of fields to the table."""
        for index, value in enumerate(row):
            width = len(str(value))
            try:
                self.widths[index] = max(self.widths[index], width)
            except IndexError:
                self.widths.append(width)
        self.rows.append(row)

    def sort(self, *sorta, **sortkw):
        header = None if self.header is None else self.rows.pop(0)
        self.rows.sort(*sorta, **sortkw)
        if header is not None:
            self.rows.insert(0, header)

    def write_csv(self, file):
        writer = csv.writer(file)
        for row in self.rows:
            writer.writerow([str(c) for c in row])

    def render(self, column_sep=" ", just_key=[]):
        """Renders and returns the full table with whitespace-padded columns."""
        col_just = [self.JUST_MAP["l"]] * len(self.widths)  # init all
        for index, key in enumerate(just_key):
            col_just[index] = self.JUST_MAP[key]
        table = []
        for row in self.rows:
            padded = []
            for index, value in enumerate(row):
                just = col_just[index]
                width = min(self.widths[index], self.max_col_width)
                padded.append(getattr(str(value), just)(width))
            table.append(column_sep.join(padded).rstrip())
        return "\n".join(table) + "\n"
