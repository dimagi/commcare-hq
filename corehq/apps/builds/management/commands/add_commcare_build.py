from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.builds.models import CommCareBuild


class Command(BaseCommand):
    help = ('Adds a commcare build, labeled with the version (x.y.z) and build_number (an incrementing integer)\n'
            'to get started see https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/builds/README.md')

    def add_arguments(self, parser):
        parser.add_argument('build_path')
        parser.add_argument('version')
        parser.add_argument('build_number')

    def handle(self, build_path, version, build_number, **options):
        try:
            build_number = int(build_number)
        except ValueError:
            raise CommandError("Build Number %r is not an integer" % build_number)

        try:
            CommCareBuild.create_from_zip(build_path, version, build_number)
        except Exception as e:
            raise CommandError("%s" % e)
        self.stdout.write('Build %s #%s created\n' % (version, build_number))
        self.stdout.write('You can see a list of builds at [your-server]/builds/\n')
