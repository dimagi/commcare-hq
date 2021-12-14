from dateutil.parser import parse

from django.core.management.base import BaseCommand

from corehq.apps.export.dbaccessors import get_brief_exports


class Command(BaseCommand):
    help = "Give stats on OData feeds"

    def add_arguments(self, parser):
        parser.add_argument(
            'path_to_log',
        )
        parser.add_argument(
            'domain',
        )

    def handle(self, path_to_log, domain, **options):
        with open(path_to_log) as file:
            logs = file.readlines()

        summary = {}
        for log in logs:
            if 'v0.5/odata' in log and '$metadata?' in log:
                data = log.split(',')
                date = parse(data[0])
                export_id = data[-1].replace(f'/a/{domain}/api/v0.5/odata/forms/', '').replace('/$metadata?', '').strip()
                if export_id not in summary:
                    summary[export_id] = date
                elif date > summary[export_id]:
                    summary[export_id] = date

        odata_feeds = [e for e in get_brief_exports(domain, None) if e['is_odata_config']]
        if not odata_feeds:
            self.stdout.write(f'The project {domain} has no active OData Feeds!')
            self.stdout.write(f'OData feeds IDs that were accessed in the past year:')
            for export_id, date_accessed in summary.items():
                self.stdout.write(f'{export_id} \t {date_accessed}')
            return

        id_to_name = {e['_id']:e['name'] for e in odata_feeds}
        for export_id, name in id_to_name.items():
            date_accessed = summary.get(export_id, 'more than 1 year ago')
            self.stdout.write(f'{export_id}\t{date_accessed}\t{export_id}')
