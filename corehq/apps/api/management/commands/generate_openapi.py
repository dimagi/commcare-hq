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


def _spec_filenames(documents):
    return {f'{name}.json' for name in documents}


def orphaned_specs(spec_dir, documents):
    """Committed ``*.json`` files under ``spec_dir`` that ``documents``
    (a ``build_all()`` result) no longer generates -- e.g. left behind
    by a renamed or removed ``doc_slug``."""
    if not spec_dir.exists():
        return []
    wanted = _spec_filenames(documents)
    return sorted(
        path for path in spec_dir.glob('*.json') if path.name not in wanted
    )


def write_specs(spec_dir):
    """Write every generated spec, and delete any committed spec file
    that is no longer generated, so a renamed or removed ``doc_slug``
    doesn't leave a stale file behind that keeps rendering forever.

    Returns ``(written, pruned)``.
    """
    spec_dir.mkdir(parents=True, exist_ok=True)
    documents = build_all()
    written = []
    for name, document in documents.items():
        path = spec_dir / f'{name}.json'
        path.write_text(serialize(document))
        written.append(path)
    pruned = orphaned_specs(spec_dir, documents)
    for path in pruned:
        path.unlink()
    return written, pruned


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
            documents = build_all()
            stale = [
                name
                for name, document in documents.items()
                if not (SPEC_DIR / f'{name}.json').exists()
                or (SPEC_DIR / f'{name}.json').read_text()
                != serialize(document)
            ]
            orphans = orphaned_specs(SPEC_DIR, documents)
            if stale or orphans:
                messages = []
                if stale:
                    messages.append(
                        'out of date: ' + ', '.join(sorted(stale))
                    )
                if orphans:
                    messages.append(
                        'orphaned (no longer generated): '
                        + ', '.join(path.name for path in orphans)
                    )
                raise CommandError(
                    'These specs are '
                    + '; '.join(messages)
                    + '. Run ./manage.py generate_openapi.'
                )
            self.stdout.write('OpenAPI specs are up to date.')
            return
        written, pruned = write_specs(SPEC_DIR)
        for path in written:
            self.stdout.write(f'wrote {path}')
        for path in pruned:
            self.stdout.write(f'removed {path} (no longer generated)')
