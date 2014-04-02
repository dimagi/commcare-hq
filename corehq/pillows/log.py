import dateutil.parser
from pillowtop.listener import SQLPillow
from couchforms.models import XFormInstance
from phonelog.models import UserEntry, DeviceReportEntry


def force_list(obj_or_list):
    return obj_or_list if isinstance(obj_or_list, list) else [obj_or_list]


def get_logs(form, report_name, report_slug):
    report = form.get(report_name, {}) or {}
    if isinstance(report, list):
        return filter(None, [log.get(report_slug) for log in report])
    return report.get(report_slug, [])


class PhoneLogPillow(SQLPillow):
    document_class = XFormInstance
    couch_filter = 'phonelog/all_logs'

    def process_sql(self, doc_dict):
        xform_id = doc_dict.get('_id')
        form = doc_dict.get('form', {})
        userlogs = get_logs(form, 'user_subreport', 'user')
        UserEntry.objects.filter(xform_id=xform_id).delete()
        DeviceReportEntry.objects.filter(xform_id=xform_id).delete()
        to_save = []
        for i, log in enumerate(force_list(userlogs)):
            to_save.append(UserEntry(
                xform_id=xform_id,
                i=i,
                user_id=log["user_id"],
                username=log["username"],
                sync_token=log["sync_token"],
            ))
        UserEntry.objects.bulk_create(to_save)

        domain = doc_dict.get('domain')
        logs = get_logs(form, 'log_subreport', 'log')
        logged_in_user = None
        to_save = []
        for i, log in enumerate(force_list(logs)):
            if not log:
                continue
            if log["type"] == 'login':
                logged_in_user = log["msg"].split('-')[1]

            to_save.append(DeviceReportEntry(
                xform_id=xform_id,
                i=i,
                domain=domain,
                type=log["type"],
                msg=log["msg"],
                # must accept either date or datetime string
                date=dateutil.parser.parse(log["@date"]).replace(tzinfo=None),
                app_version=form.get('app_version'),
                device_id=form.get('device_id'),
                username=logged_in_user,
            ))
        DeviceReportEntry.objects.bulk_create(to_save)
