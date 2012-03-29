from couchdbkit.exceptions import BadValueError
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.builds.models import CommCareBuild

class Command(BaseCommand):
    args = '<build_path> <version> <build_number>'
    help = 'Adds a commcare build, labeled with the version (x.y.z) and build_number (an incrementing integer)'
    def handle(self, *args, **options):
        try:
            build_path, version, build_number = args
        except ValueError:
            raise CommandError('Usage: %s' % self.args)

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