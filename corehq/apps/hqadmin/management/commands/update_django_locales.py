import os
import shutil
from django.conf import settings
from django.core.management import BaseCommand
import django

class Command(BaseCommand):
    help = "Update django locales for three-digit codes"
    args = ""

    def handle(self, *args, **options):
        # if we were feeling ambitious we could get this from something more
        # formal/standard, but this seems totally workable for our needs
        HQ_TO_DJANGO_MAP = {
            'fra': 'fr',
            'hin': 'hi',
            'por': 'pt',
        }

        def _get_django_home():
            return os.path.abspath(os.path.dirname(django.__file__))

        def _get_django_locale_directories():
            return [
                os.path.join(_get_django_home(), 'conf', 'locale'),
                os.path.join(_get_django_home(), 'contrib', 'auth', 'locale'),
                os.path.join(_get_django_home(), 'contrib', 'humanize', 'locale'),
            ]

        print 'updating django locale files for local languages'
        locale_dirs = _get_django_locale_directories()
        for langcode, display in settings.LANGUAGES:
            for locale_dir in locale_dirs:
                path = os.path.join(locale_dir, langcode)
                if not os.path.exists(path):
                    # will intentionally fail hard since this will result in a bad locale config
                    mapped_code = HQ_TO_DJANGO_MAP[langcode]
                    django_path = os.path.join(locale_dir, mapped_code)
                    shutil.copytree(django_path, path)
                    print 'copied {src} to {dst}'.format(src=django_path, dst=path)
                else:
                    print '%s all good' % langcode
