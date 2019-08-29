from django.core.management.base import BaseCommand

from corehq.apps.builds.jadjar import sign_jar


class Command(BaseCommand):
    help = 'Signs a jad/jar pair.'

    def add_arguments(self, parser):
        parser.add_argument('jad_path')
        parser.add_argument('jar_path')

    def handle(self, jad_path, jar_path, **options):
        with open(jad_path, 'r', encoding='utf-8') as f:
            jad_file = f.read()
        with open(jar_path, 'rb') as f:
            jar_file = f.read()

        new_jad = sign_jar(jad_file, jar_file)
        with open('{}.signed'.format(jad_path), 'w', encoding='utf-8') as f:
            f.write(new_jad)

        return 'signed jad file and saved copy as [jad].signed'
