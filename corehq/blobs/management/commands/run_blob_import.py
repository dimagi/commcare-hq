import asyncio
import sys
import tarfile

from django.core.management import BaseCommand

from corehq.blobs import get_blob_db

USAGE = "Usage: ./manage.py run_blob_import <filename>"
NUM_WORKERS = 5


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, filename, **options):
        asyncio_run(import_blobs_from_tgz(filename))


async def import_blobs_from_tgz(filename):
    """
    Creates worker tasks to consume queue, and adds blobs to queue only
    as fast as they are consumed.
    """
    queue = asyncio.Queue(maxsize=NUM_WORKERS)
    worker_tasks = [asyncio.create_task(worker(queue))
                    for __ in range(NUM_WORKERS)]

    for fileobj, key in get_blobs(filename):
        await queue.put((fileobj, key))
    await queue.join()

    for task in worker_tasks:
        task.cancel()
    await asyncio.gather(*worker_tasks, return_exceptions=True)


def get_blobs(filename):
    """
    Generator to iterate blobs in tar.gz file
    """
    with tarfile.open(filename, 'r:gz') as tgzfile:
        for tarinfo in tgzfile:
            key = tarinfo.name
            fileobj = tgzfile.extractfile(tarinfo)
            yield (fileobj, key)


async def worker(queue):
    """
    Coroutine that pulls blobs off ``queue`` and copies them to blob DB.
    """
    loop = asyncio.get_running_loop()
    blob_db = get_blob_db()
    while True:
        fileobj, key = await queue.get()
        try:
            # Run blob_db.copy_blob(fileobj, key) in a separate thread
            await loop.run_in_executor(None, blob_db.copy_blob, fileobj, key)
        finally:
            fileobj.close()
            queue.task_done()


def asyncio_run(future):
    """
    Utility function for Python < 3.7
    """
    if sys.version_info >= (3, 7, 0):
        return asyncio.run(future)
    loop = asyncio.get_event_loop()
    try:
        return loop.run_until_complete(future)
    finally:
        loop.close()
