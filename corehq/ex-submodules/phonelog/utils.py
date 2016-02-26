from django.db import transaction
from corehq.apps.users.util import format_username
from corehq.apps.users.dbaccessors import get_user_id_by_username
from .models import UserEntry, DeviceReportEntry, UserErrorEntry


def device_users_by_xform(xform_id):
    return list(
        UserEntry.objects.filter(xform_id__exact=xform_id)
        .distinct('username').values_list('username', flat=True)
    )


def _force_list(obj_or_list):
    return obj_or_list if isinstance(obj_or_list, list) else [obj_or_list]


def _get_logs(form, report_name, report_slug):
    report = form.get(report_name, {}) or {}
    if isinstance(report, list):
        return filter(None, [log.get(report_slug) for log in report])
    return report.get(report_slug, [])


@transaction.atomic
def process_device_log(domain, xform):
    _process_user_subreport(xform)
    _process_log_subreport(domain, xform)
    _process_user_error_subreport(domain, xform)


def _process_user_subreport(xform):
    userlogs = _get_logs(xform.form_data, 'user_subreport', 'user')
    UserEntry.objects.filter(xform_id=xform.form_id).delete()
    DeviceReportEntry.objects.filter(xform_id=xform.form_id).delete()
    to_save = []
    for i, log in enumerate(_force_list(userlogs)):
        to_save.append(UserEntry(
            xform_id=xform.form_id,
            i=i,
            user_id=log["user_id"],
            username=log["username"],
            sync_token=log["sync_token"],
        ))
    UserEntry.objects.bulk_create(to_save)


def _process_log_subreport(domain, xform):
    form_data = xform.form_data
    logs = _get_logs(form_data, 'log_subreport', 'log')
    logged_in_username = None
    logged_in_user_id = None
    to_save = []
    for i, log in enumerate(_force_list(logs)):
        if not log:
            continue
        if log["type"] == 'login':
            # j2me log = user_id_prefix-username
            logged_in_username = log["msg"].split('-')[1]
            cc_username = format_username(logged_in_username, domain)
            logged_in_user_id = get_user_id_by_username(cc_username)
        elif log["type"] == 'user' and log["msg"][:5] == 'login':
            # android log = login|username|user_id
            msg_split = log["msg"].split('|')
            logged_in_username = msg_split[1]
            logged_in_user_id = msg_split[2]

        to_save.append(DeviceReportEntry(
            xform_id=xform.form_id,
            i=i,
            domain=domain,
            type=log["type"],
            msg=log["msg"],
            # must accept either date or datetime string
            date=log["@date"],
            server_date=xform.received_on,
            app_version=form_data.get('app_version'),
            device_id=form_data.get('device_id'),
            username=logged_in_username,
            user_id=logged_in_user_id,
        ))
    DeviceReportEntry.objects.bulk_create(to_save)


def _process_user_error_subreport(domain, xform):
    errors = _get_logs(xform.form_data, 'user_error_subreport', 'user_error')
    to_save = []
    for i, error in enumerate(errors):
        entry = UserErrorEntry(
            domain=domain,
            xform_id=xform.form_id,
            i=i,
            app_id=error['app_id'],
            version_number=int(error['version']),
            date=error["@date"],
            server_date=xform.received_on,
            user_id=error['user_id'],
            expr=error['expr'],
            msg=error['msg'],
            session=error['session'],
            type=error['type'],
        )
        to_save.append(entry)
    UserErrorEntry.objects.bulk_create(to_save)
