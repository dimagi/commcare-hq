from celery import task
from soil import DownloadBase
from corehq.util.zip_utils import make_zip_tempfile_async


@task
def make_zip_tempfile_task(include_multimedia_files, include_index_files, app, download_id, compress_zip=True):
    DownloadBase.set_progress(make_zip_tempfile_task, 0, 100)
    make_zip_tempfile_async(include_multimedia_files, include_index_files, app, compress_zip, download_id)
    DownloadBase.set_progress(make_zip_tempfile_task, 100, 100)
