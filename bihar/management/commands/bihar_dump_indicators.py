from django.core.management import BaseCommand
from bihar.utils import get_all_calculations


class Command(BaseCommand):
    """Nice to pipe this into pbcopy (mac only?) and then paste into excel"""
    def handle(self, *args, **options):
        group_id = args[0]
        lines = get_all_calculations(group_id)
        for line in lines:
            print '\t'.join(map(unicode, line))