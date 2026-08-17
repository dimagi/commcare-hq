"""Write the committed OpenAPI specs for the CommCare data APIs."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.api.openapi.builder import build_all

SPEC_DIR = Path(settings.BASE_DIR) / 'docs' / 'api' / 'spec'


def serialize(document):
    """Deterministic JSON, so that regeneration produces no spurious diff."""
    return json.dumps(document, indent=2, sort_keys=True) + '\n'


def write_specs(spec_dir):
    spec_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, document in build_all().items():
        path = spec_dir / f'{name}.json'
        path.write_text(serialize(document))
        written.append(path)
    return written


class Command(BaseCommand):
    help = 'Generate the OpenAPI specs for the CommCare data APIs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Exit non-zero if the committed specs are out of date, '
            'without writing anything.',
        )

    def handle(self, **options):
        if options['check']:
            stale = [
                name
                for name, document in build_all().items()
                if not (SPEC_DIR / f'{name}.json').exists()
                or (SPEC_DIR / f'{name}.json').read_text()
                != serialize(document)
            ]
            if stale:
                raise CommandError(
                    'These specs are out of date: '
                    + ', '.join(sorted(stale))
                    + '. Run ./manage.py generate_openapi.'
                )
            self.stdout.write('OpenAPI specs are up to date.')
            return
        for path in write_specs(SPEC_DIR):
            self.stdout.write(f'wrote {path}')
