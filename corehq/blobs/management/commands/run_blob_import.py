import tarfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from django.core.management import BaseCommand

from corehq.blobs import get_blob_db

USAGE = "Usage: ./manage.py run_blob_import <filename>"
NUM_WORKERS = 5


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, filename, **options):
        import_blobs_from_tgz(filename)


def import_blobs_from_tgz(filename):
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        func = partial(worker, filename)
        futures = executor.map(func, range(NUM_WORKERS))
        list(futures)  # Resolves results and exceptions from workers


def worker(filename, worker_number):
    """
    Each worker claims the ``worker_number``th file in the ``filename``
    tar.gz file, and copies it to blob_db.

    Iterated file handles for blobs cannot be passed to coroutines or
    futures, because as soon as the caller iterates to the next blob,
    the previous handle is closed. We could read the data and pass that,
    but blobs can be too big to read at once.

    So threaded workers all need to read the same tar.gz file and
    iterate the files inside it, picking out the ones that belong to
    them.
    """
    # ^^^ Yeah, not great. Maybe filesystem caching helps.
    blob_db = get_blob_db()
    with tarfile.open(filename, 'r:gz') as tgzfile:
        for i, tarinfo in enumerate(tgzfile):
            if i % NUM_WORKERS == worker_number:
                key = tarinfo.name
                fileobj = tgzfile.extractfile(tarinfo)
                blob_db.copy_blob(fileobj, key)
