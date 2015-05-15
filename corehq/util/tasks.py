from celery import task
from soil import DownloadBase
from corehq.apps.hqmedia.views import make_zip_tempfile_async


@task
def make_zip_tempfile_task(*args, **kwargs):
    DownloadBase.set_progress(make_zip_tempfile_task, 0, 100)
    response, errors = make_zip_tempfile_async(*args, **kwargs)
    DownloadBase.set_progress(make_zip_tempfile_task, 100, 100)
    return {
        "errors": errors,
    }
