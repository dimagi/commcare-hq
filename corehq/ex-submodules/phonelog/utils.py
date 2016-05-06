from django.db import transaction
from corehq.apps.users.util import format_username
from corehq.apps.users.dbaccessors import get_user_id_by_username
from .models import UserEntry, DeviceReportEntry, UserErrorEntry, ForceCloseEntry


def device_users_by_xform(xform_id):
    return list(
        UserEntry.objects.filter(xform_id__exact=xform_id)
        .distinct('username').values_list('username', flat=True)
    )


def _force_list(obj_or_list):
    return obj_or_list if isinstance(obj_or_list, list) else [obj_or_list]


def _get_log_entries(report, report_slug):
    for subreport in report:
        # subreport should be {"log": <one or more entry models>}
        if isinstance(subreport, dict) and report_slug in subreport:
            entry_or_entries = subreport.get(report_slug)
            if isinstance(entry_or_entries, list):
                for entry in entry_or_entries:
                    yield entry
            else:
                yield entry_or_entries


def _get_logs(form, report_name, report_slug):
    """
    Returns a list of log entries matching report_name.report_slug
    These entries are 1-to-1 with the phonelog models (DeviceReportEntry,
    UserErrorEntry, UserEntry).
    """
    report = form.get(report_name, {}) or {}
    if isinstance(report, list):
        return list(_get_log_entries(report, report_slug))
    return _force_list(report.get(report_slug, []))


@transaction.atomic
def process_device_log(domain, xform):
    _process_user_subreport(xform)
    _process_log_subreport(domain, xform)
    _process_user_error_subreport(domain, xform)
    _process_force_close_subreport(domain, xform)


def _process_user_subreport(xform):
    userlogs = _get_logs(xform.form_data, 'user_subreport', 'user')
    UserEntry.objects.filter(xform_id=xform.form_id).delete()
    DeviceReportEntry.objects.filter(xform_id=xform.form_id).delete()
    to_save = []
    for i, log in enumerate(userlogs):
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
    for i, log in enumerate(logs):
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
        # beta versions have 'version', but the name should now be 'app_build'.
        # Probably fine to remove after June 2016.
        version = error['app_build'] if 'app_build' in error else error['version']
        entry = UserErrorEntry(
            domain=domain,
            xform_id=xform.form_id,
            i=i,
            app_id=error['app_id'],
            version_number=int(version),
            date=error["@date"],
            server_date=xform.received_on,
            user_id=error['user_id'],
            expr=error['expr'],
            msg=error['msg'],
            session=error['session'],
            type=error['type'],
            context_node=error.get('context_node', ''),
        )
        to_save.append(entry)
    UserErrorEntry.objects.bulk_create(to_save)


def _process_force_close_subreport(domain, xform):
    force_closures = _get_logs(xform.form_data, 'force_close_subreport', 'force_close')
    to_save = []
    for force_closure in force_closures:
        # There are some testing versions going around with an outdated schema
        # This never made it into an official release, but:
        # app_id and user_id might be missing
        # early versions have 'build_number' - the name should now be 'app_build'
        # All of this is probably fine to remove after, say June 2016.
        version = (force_closure['app_build'] if 'app_build' in force_closure
                   else force_closure['build_number'])
        entry = ForceCloseEntry(
            domain=domain,
            xform_id=xform.form_id,
            app_id=force_closure.get('app_id'),
            version_number=int(version),
            date=force_closure["@date"],
            server_date=xform.received_on,
            user_id=force_closure.get('user_id'),
            type=force_closure['type'],
            msg=force_closure['msg'],
            android_version=force_closure['android_version'],
            device_model=force_closure['device_model'],
            session_readable=force_closure['session_readable'],
            session_serialized=force_closure['session_serialized'],
        )
        to_save.append(entry)
    ForceCloseEntry.objects.bulk_create(to_save)
