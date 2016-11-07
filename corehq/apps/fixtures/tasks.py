from corehq.apps.fixtures.upload import upload_fixture_file
from corehq.util.celery_utils import hqtask
from soil import DownloadBase


@hqtask()
def fixture_upload_async(domain, download_id, replace):
    task = fixture_upload_async
    DownloadBase.set_progress(task, 0, 100)
    download_ref = DownloadBase.get(download_id)
    result = upload_fixture_file(domain, download_ref.get_filename(), replace, task)
    DownloadBase.set_progress(task, 100, 100)
    return {
        'messages': result,
    }


@hqtask()
def fixture_download_async(prepare_download, *args, **kw):
    task = fixture_download_async
    DownloadBase.set_progress(task, 0, 100)
    prepare_download(task=task, *args, **kw)
    DownloadBase.set_progress(task, 100, 100)
