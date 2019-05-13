from __future__ import absolute_import, unicode_literals

from celery.task import task

from soil import DownloadBase

from corehq.apps.fixtures.download import prepare_fixture_download
from corehq.apps.fixtures.models import FixtureDataItem, FixtureOwnership
from corehq.apps.fixtures.upload import upload_fixture_file


@task
def fixture_upload_async(domain, download_id, replace, skip_orm):
    task = fixture_upload_async
    DownloadBase.set_progress(task, 0, 100)
    download_ref = DownloadBase.get(download_id)
    result = upload_fixture_file(domain, download_ref.get_filename(), replace, task, skip_orm)
    DownloadBase.set_progress(task, 100, 100)
    return {
        'messages': {
            'success': result.success,
            'messages': result.messages,
            'errors': result.errors,
            'number_of_fixtures': result.number_of_fixtures,
        },
    }


@task(serializer='pickle')
def fixture_download_async(prepare_download, *args, **kw):
    # deprecated task. no longer called. to be removed after all tasks consumed
    task = fixture_download_async
    DownloadBase.set_progress(task, 0, 100)
    prepare_download(task=task, *args, **kw)
    DownloadBase.set_progress(task, 100, 100)


@task
def async_fixture_download(table_ids, domain, download_id):
    task = async_fixture_download
    DownloadBase.set_progress(task, 0, 100)
    prepare_fixture_download(table_ids, domain, task, download_id)
    DownloadBase.set_progress(task, 100, 100)


# this task is likely to fail if view has not been hit recently
# should be retried
@task(queue='background_queue')
def delete_unneeded_fixture_data_item(domain, data_type_id):
    item_ids = []
    for item in FixtureDataItem.by_data_type(domain, data_type_id):
        item.delete()
        item_ids.append(item.get_id)
    for doc in FixtureOwnership.for_all_item_ids(item_ids, domain):
        doc.delete()
