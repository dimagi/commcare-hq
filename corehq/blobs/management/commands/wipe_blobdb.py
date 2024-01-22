from django.core.management import BaseCommand

from corehq.apps.cleanup.utils import confirm_destructive_operation
from corehq.blobs import get_blob_db
from corehq.blobs.models import BlobMeta
from corehq.sql_db.util import get_db_aliases_for_partitioned_query

CHUNK_SIZE = 1000


class Command(BaseCommand):
    """
    Wipe all data from BlobDB.
    """
    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )

    def handle(self, *args, **options):
        confirm_destructive_operation()
        bytes_deleted = wipe_blobdb(options['commit'])

        print(f"Deleted {bytes_deleted} bytes.")
        if not options['commit']:
            print("You need to run with --commit for the deletion to happen.")


def wipe_blobdb(commit=False):
    bytes_deleted = 0
    blob_db = get_blob_db()
    for dbname in get_db_aliases_for_partitioned_query():
        bytes_deleted += wipe_shard(blob_db, dbname, commit)
    return bytes_deleted


def wipe_shard(blob_db, dbname, commit=False):
    bytes_deleted = 0
    metas = BlobMeta.objects.using(dbname).order_by('id').all()
    for chunk in cursor_paginated(metas, CHUNK_SIZE):
        if commit:
            blob_db.bulk_delete(metas=chunk)
        bytes_deleted += sum(meta.content_length for meta in chunk)
    return bytes_deleted


def cursor_paginated(queryset, page_size):
    """
    Paginates using auto-incremented integer primary key ``id`` instead
    of offset (not an actual database cursor).

    Credit: http://cra.mr/2011/03/08/building-cursors-for-the-disqus-api
    """
    next_id = 0
    while True:
        page = list(queryset.filter(id__gte=next_id)[:page_size])
        if not page:
            return
        yield page
        if len(page) < page_size:
            return
        next_id = page[-1].id + 1
