import datetime

from django.conf import settings
from django.template.loader import render_to_string

from celery.task import task

from dimagi.utils.chunked import chunked
from soil import DownloadBase

from corehq.apps.fixtures.download import prepare_fixture_download
from corehq.apps.fixtures.models import FixtureDataItem, FixtureOwnership
from corehq.apps.fixtures.upload import upload_fixture_file
from corehq.apps.hqwebapp.tasks import send_html_email_async


@task
def fixture_upload_async(domain, download_id, replace, skip_orm, user_email=None):
    task = fixture_upload_async
    DownloadBase.set_progress(task, 0, 100)
    download_ref = DownloadBase.get(download_id)
    time_start = datetime.datetime.now()
    result = upload_fixture_file(domain, download_ref.get_filename(), replace, task, skip_orm)
    time_end = datetime.datetime.now()
    DownloadBase.set_progress(task, 100, 100)
    messages = {
        'success': result.success,
        'messages': result.messages,
        'errors': result.errors,
        'number_of_fixtures': result.number_of_fixtures
    }
    if user_email:
        send_upload_fixture_complete_email(user_email, domain, time_start, time_end, messages)
    return {
        'messages': messages,
    }


def send_upload_fixture_complete_email(email, domain, time_start, time_end, messages):
    context = {
        "username": email,
        "domain": domain,
        "time_start": time_start,
        "time_end": time_end,
        "messages": messages
    }
    send_html_email_async.delay(
        "Your fixture upload is complete!",
        email,
        render_to_string('fixtures/upload_complete.html', context),
        render_to_string('fixtures/upload_complete.txt', context),
        email_from=settings.DEFAULT_FROM_EMAIL
    )
    return


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


@task(queue='background_queue', bind=True, default_retry_delay=15 * 60)
def delete_unneeded_fixture_data_item(self, domain, data_type_id):
    """Deletes all fixture data items and their ownership models based on their data type.

    Note that this does not bust any caches meaning that the data items could still
    be returned to the user for some time
    """
    item_ids = []
    try:
        for items in chunked(FixtureDataItem.by_data_type(domain, data_type_id), 1000):
            FixtureDataItem.delete_docs(items)
            item_ids.extend([item.get_id for item in items])
        for item_id_chunk in chunked(item_ids, 1000):
            for docs in chunked(FixtureOwnership.for_all_item_ids(item_id_chunk, domain), 1000):
                FixtureOwnership.delete_docs(docs)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        # there's no base exception in couchdbkit to catch, so must use Exception
        self.retry(exc=exc)
