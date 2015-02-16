from django.core.management.base import BaseCommand, CommandError
from corehq.apps.builds.jadjar import sign_jar


class Command(BaseCommand):
    args = '<jad_path> <jar_path>'
    help = 'Signs a jad/jar pair.'

    def handle(self, *args, **options):
        try:
            jad_path, jar_path = args
        except ValueError:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        with open(jad_path, 'r') as f:
            jad_file = f.read()
        with open(jar_path, 'rb') as f:
            jar_file = f.read()

        new_jad = sign_jar(jad_file, jar_file)
        with open('{}.signed'.format(jad_path), 'w') as f:
            f.write(new_jad)

        return 'signed jad file and saved copy as [jad].signed'
