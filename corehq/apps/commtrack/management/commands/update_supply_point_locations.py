from django.core.management.base import BaseCommand
from casexml.apps.case.models import CommCareCase
from corehq.util.couch import iter_update, DocUpdate


class Command(BaseCommand):
    help = ("Make sure all supply point cases have their owner_id set "
            "to the location_id")

    def handle(self, *args, **options):
        def add_location(case):
            if not case['location_id']:
                return None
            if case['owner_id'] != case['location_id']:
                case['owner_id'] = case['location_id']
                return DocUpdate(case)

        iter_update(
            CommCareCase.get_db(),
            add_location,
            self.get_case_ids(),
            verbose=True
        )

    def get_case_ids(self):
        return (case['id'] for case in CommCareCase.get_db().view(
            'commtrack/supply_point_by_loc',
            reduce=False,
            include_docs=False,
        ).all())
