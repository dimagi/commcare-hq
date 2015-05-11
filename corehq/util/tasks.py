from celery import task
from soil import DownloadBase
from corehq.util.zip_utils import make_zip_tempfile


@task
def make_zip_tempfile_async(files, download_id, compress=True):
    # task = make_zip_tempfile_async
    DownloadBase.set_progress(make_zip_tempfile_async, 0, 100)
    make_zip_tempfile(files, compress, download_id)
    DownloadBase.set_progress(make_zip_tempfile_async, 100, 100)
