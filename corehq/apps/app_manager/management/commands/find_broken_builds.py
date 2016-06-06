from optparse import make_option
from couchdbkit.exceptions import ResourceNotFound
from django.core.management import BaseCommand
from django.core.management.base import CommandError
from corehq.apps.app_manager.exceptions import SuiteValidationError
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.suite_xml.utils import validate_suite
from corehq.apps.app_manager.xform import XForm
from corehq.blobs.mixin import BlobHelper
from dimagi.utils.couch.database import iter_docs


def premature_auto_gps(build):
    app = Application.wrap(build)
    if app.build_version >= '2.14':
        return

    for module in app.get_modules():
        for form in module.get_forms():
            try:
                built_source = app.fetch_attachment(
                    'files/modules-{}/forms-{}.xml'.format(module.id, form.id))
            except ResourceNotFound:
                continue
            if form.get_auto_gps_capture():
                return 'auto gps error'
            elif XForm(built_source).model_node.find("{orx}pollsensor"):
                return 'auto gps error'


def form_filter_error(build):
    app = Application.wrap(build)
    modules = app.get_modules()
    for mod in modules:
        forms = mod.get_forms()
        prev_form_filter = False
        for form in forms:
            form_filter = hasattr(form, 'form_filter') and form.form_filter
            if form_filter and not prev_form_filter and form.id > 0:
                return 'form filter error'
            prev_form_filter = form_filter


def broken_suite_files(build):
    db = Application.get_db()
    error = None
    try:
        suite = BlobHelper(build, db).fetch_attachment('files/suite.xml')
    except ResourceNotFound:
        error = 'build has no attachment files/suite.xml'
    else:
        try:
            validate_suite(suite)
        except SuiteValidationError as error:
            pass
    if error:
        yield '%s\t%s\t%s\t%s\t%s\n' % (
            build.get('built_on'),
            build.get('domain'),
            build['_id'],
            build.get('copy_of'),
            error,
        )


CHECK_FUNCTIONS = {
    'broken_suite_files': broken_suite_files,
    'form_filter_error': form_filter_error,
    'premature_auto_gps': premature_auto_gps,
}


class Command(BaseCommand):
    help = "Print a list of broken builds"
    args = '<check_function>'
    option_list = BaseCommand.option_list + (
        make_option('--ids',
                    action='store',
                    dest='build_ids',
                    default='',
                    help='Comma-separated list of Application IDs to check'),
        make_option('--start',
                    action='store',
                    dest='startdate',
                    default='',
                    help='Start date'),
        make_option('--end',
                    action='store',
                    dest='enddate',
                    default='',
                    help='End date'),
    )

    def handle(self, *args, **options):
        args = list(args)
        valid_functions = ', '.join(CHECK_FUNCTIONS.keys())
        if not args:
            raise CommandError('Usage is find_broken_builds %s. Options are: %s' % (
                self.args,
                valid_functions
            ))

        check_fn_name = args[0]
        check_fn = CHECK_FUNCTIONS.get(check_fn_name)
        if not check_fn:
            raise CommandError('Unrecognised check function. Options are: %s' % valid_functions)

        start = options['startdate']
        end = options['enddate']
        ids = options['build_ids']

        print 'Starting...\n'
        if not ids:
            ids = get_build_ids(start, end)
        else:
            ids = ids.split(',')

        print 'Checking {} builds\n'.format(len(ids))
        for message in find_broken_builds(check_fn, ids):
            self.stderr.write(message)


def get_build_ids(start, end):
    builds_ids = Application.view(
        'app_manager/builds_by_date',
        startkey=start,
        endkey=end,
        reduce=False,
        wrapper=lambda row: row['id']
    ).all()
    return builds_ids


def find_broken_builds(checker, builds_ids):
    for build in iter_docs(Application.get_db(), builds_ids):
        error = checker(build)
        if error:
            yield '%s\t%s\t%s\t%s\t%s\n' % (
                build.get('built_on'),
                build.get('domain'),
                build['_id'],
                build.get('copy_of'),
                error,
            )
