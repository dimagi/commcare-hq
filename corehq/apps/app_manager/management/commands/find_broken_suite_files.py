from django.core.management import BaseCommand
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager import suite_xml


def find_broken_suite_files(start, end):
    db = Application.get_db()
    build_ids = db.view(
        'app_manager/builds_by_date',
        startkey=start,
        endkey=end,
        reduce=False,
        wrapper=lambda row: row['id']
    ).all()
    for build_id in build_ids:
        suite = db.fetch_attachment(build_id, 'files/suite.xml')
        try:
            suite_xml.validate_suite(suite)
        except suite_xml.SuiteValidationError as error:
            build = db.get(build_id)
            yield '%s\t%s\t%s\n' % (build.get('domain'), build_id, error)
    yield 'Done.'


class Command(BaseCommand):
    def handle(self, *args, **options):
        args = list(args)
        start, end = (args.pop(0), args.pop(0))
        for message in find_broken_suite_files(start, end):
            self.stderr.write(message)
