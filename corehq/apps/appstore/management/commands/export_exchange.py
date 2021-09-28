import csv

from datetime import datetime
from django.core.management.base import BaseCommand

from corehq.apps.appstore.exceptions import CopiedFromDeletedException
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser
from dimagi.utils.parsing import ISO_DATETIME_FORMAT


class Command(BaseCommand):
    help = """
        Pulls data on domain snapshots (projects in the late CommCare Exchange).
    """

    def add_arguments(self, parser):
        parser.add_argument('outfile')

    def handle(self, outfile, **options):
        snapshots = Domain.get_db().view(
            'domain/snapshots',
            startkey=[],
            endkey=[{}],
            reduce=False,
            include_docs=True,
        ).all()
        snapshots = [s['doc'] for s in snapshots]
        snapshots = [s for s in snapshots if s['published'] and s['is_snapshot'] and s.get('snapshot_head')]
        rows = [[
            'Snapshot Domain',
            'Original Domain',
            'Project Title',
            'Organization',
            'Summary',
            'Category',
            'Published By',
            'Published On',
            'Languages',
            'License',
        ]]
        for s in snapshots:
            domain = Domain.wrap(s)
            user = None
            if s['cda']['user_id']:
                user = CouchUser.get_by_user_id(s['cda']['user_id'])
            author = s['author']
            if not author and user:
                author = user.human_friendly_name
            try:
                copied_from = domain.copied_from.name
            except CopiedFromDeletedException:
                copied_from = "MISSING"
            row = (
                domain.name,
                copied_from,
                s['title'],
                author,
                s['short_description'],
                s['project_type'],
                user.username if user else None,
                datetime.strptime(s['snapshot_time'], ISO_DATETIME_FORMAT).strftime('%b %d, %Y'),
                ', '.join(set([lang for app in domain.applications() for lang in app.langs])),
                s['license'],
            )
            rows.append(row)

        with open(outfile, 'w', encoding='utf-8') as out:
            writer = csv.writer(out, delimiter="\t")
            for row in rows:
                writer.writerow(row)
