from lxml import etree
from django.core.management import BaseCommand
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager import suite_xml


class Command(BaseCommand):
    def handle(self, *args, **options):
        args = list(args)
        start, end = (args.pop(0), args.pop(0))
        db = Application.get_db()
        build_ids = db.view(
            'app_manager/builds_by_date',
            startkey=start,
            endkey=end,
            reduce=False,
            wrapper=lambda row: row['id']
        ).all()
        for build_id in build_ids:
            self.stdout.write('%s\n' % build_id)
            suite = db.fetch_attachment(build_id, 'files/suite.xml')
            try:
                suite_xml.validate_suite(suite)
            except suite_xml.SuiteValidationError as error:
                self.log_validation_error(build_id, error)

    def log_validation_error(self, build_id, error):
        self.stderr.write('%s: %s' % (build_id, error))
