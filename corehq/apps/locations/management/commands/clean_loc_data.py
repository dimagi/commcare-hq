import csv
from django.core.management.base import BaseCommand
from corehq.apps.locations.util import purge_locations


class Command(BaseCommand):
    args = "<CSV file>"
    help = ("Wipe LocationType, Location, SQLLocation, and StockState data "
            "from a list of domains.\n"
            "Pass in a csv file where the first column is a list of domains.")

    def handle(self, *args, **options):
        if not len(args) == 1:
            print "Format is ./manage.py clean_loc_data {}".format(self.args)
            return

        filename = args[0]
        with open(filename) as f:
            reader = csv.reader(f)
            reader.next()
            domains = [row[0] for row in reader]

        msg = ("Are you sure you'd like to clean the following domains?\n"
               "{}\n(y/n)".format("\n".join(domains)))
        if raw_input(msg) != 'y':
            return

        for domain in domains:
            purge_locations(domain)
