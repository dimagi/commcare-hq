import datetime

from django.template.loader import render_to_string

from soil import DownloadBase

from corehq.apps.celery import task
from corehq.apps.fixtures.download import prepare_fixture_download
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
        domain=domain,
        use_domain_gateway=True,
    )
    return


@task
def async_fixture_download(table_ids, domain, download_id, owner_id):
    task = async_fixture_download
    DownloadBase.set_progress(task, 0, 100)
    prepare_fixture_download(table_ids, domain, task, download_id, owner_id)
    DownloadBase.set_progress(task, 100, 100)
