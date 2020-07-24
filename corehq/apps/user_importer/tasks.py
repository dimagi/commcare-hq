import functools

from celery.task import task

from django.db import DEFAULT_DB_ALIAS

from soil import DownloadBase

from corehq.apps.user_importer.models import UserUploadRecord


@task(serializer='pickle')
def import_users_and_groups(domain, user_specs, group_specs, upload_user, upload_record_id):
    from corehq.apps.user_importer.importer import create_or_update_users_and_groups, create_or_update_groups
    task = import_users_and_groups
    DownloadBase.set_progress(task, 0, 100)

    total = len(user_specs) + len(group_specs)
    DownloadBase.set_progress(task, 0, total)

    group_memoizer, group_results = create_or_update_groups(domain, group_specs)

    DownloadBase.set_progress(task, len(group_specs), total)

    def _update_progress(value, start=0):
        DownloadBase.set_progress(task, start + value, total)

    user_results = create_or_update_users_and_groups(
        domain,
        user_specs,
        upload_user=upload_user,
        group_memoizer=group_memoizer,
        update_progress=functools.partial(_update_progress, start=len(group_specs))
    )
    results = {
        'errors': group_results['errors'] + user_results['errors'],
        'rows': user_results['rows']
    }
    upload_record = UserUploadRecord.objects.using(DEFAULT_DB_ALIAS).get(pk=upload_record_id)
    upload_record.task_id = import_users_and_groups.request.id
    upload_record.status = results
    upload_record.save()
    DownloadBase.set_progress(task, total, total)
    return {
        'messages': results
    }
