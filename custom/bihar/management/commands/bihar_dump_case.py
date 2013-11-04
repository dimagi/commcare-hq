import json
from django.core.management import BaseCommand
from custom.bihar.models import BiharCase


class Command(BaseCommand):
    """
    Dumps a case to a json file for testing.
    """

    def handle(self, *args, **options):
        case_id = args[0]
        filename = args[1]
        case = BiharCase.get(case_id)

        with open(filename, 'w') as f:
            f.write(json.dumps(case.dump_json(), indent=2))
