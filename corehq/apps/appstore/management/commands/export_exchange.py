import csv
import logging

from datetime import datetime
from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser
from dimagi.utils.parsing import ISO_DATE_FORMAT, ISO_DATETIME_FORMAT


class Command(BaseCommand):
    help = """
    """

    def add_arguments(self, parser):
        parser.add_argument('outfile')

    def handle(self, outfile, **options):
        snapshots = Domain.get_db().view('domain/snapshots', startkey=[], endkey=[{}], reduce=False, include_docs=True,).all()
        snapshots = [s['doc'] for s in snapshots]
        snapshots = [s for s in snapshots if s['published'] and s['is_snapshot'] and s.get('snapshot_head')]
        rows = [
            (
                s['title'],
                s['author'] or Domain.wrap(s).name_of_publisher,
                s['short_description'],
                s['project_type'],
                CouchUser.get_by_user_id(s['cda']['user_id']).username if s['cda']['user_id'] and CouchUser.get_by_user_id(s['cda']['user_id']) else None,
                datetime.strptime(s['snapshot_time'], ISO_DATETIME_FORMAT).strftime('%b %d, %Y'),
                Domain.wrap(s).readable_languages(),
                s['license'],
            )
            for s in snapshots
        ]

        with open(outfile, 'w', encoding='utf-8') as out:
            writer = csv.writer(out, delimiter="~")
            for row in rows:
                writer.writerow(row)
