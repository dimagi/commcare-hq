from celery import task
from soil import DownloadBase
from corehq.util.zip_utils import make_zip_tempfile_async


@task
def make_zip_tempfile_task(*args, **kwargs):
    DownloadBase.set_progress(make_zip_tempfile_task, 0, 100)
    make_zip_tempfile_async(*args, **kwargs)
    DownloadBase.set_progress(make_zip_tempfile_task, 100, 100)
