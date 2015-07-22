from celery.utils.functional import memoize
import dateutil.parser
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from dimagi.utils.parsing import string_to_utc_datetime
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

    @memoize(maxsize=2048)
    def get_user_id(self, username, domain):
        cc_username = format_username(username, domain)
        result = CouchUser.view(
            'users/by_username',
            key=cc_username,
            include_docs=False,
            reduce=False,
        )
        row = result.one()
        if row:
            return row["id"]

    def process_sql(self, doc_dict, delete=False):
        if delete:
            return

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
        logged_in_username = None
        logged_in_user_id = None
        to_save = []
        for i, log in enumerate(force_list(logs)):
            if not log:
                continue
            if log["type"] == 'login':
                # j2me log = user_id_prefix-username
                logged_in_username = log["msg"].split('-')[1]
                logged_in_user_id = self.get_user_id(logged_in_username, domain)
            elif log["type"] == 'user' and log["msg"][:5] == 'login':
                # android log = login|username|user_id
                msg_split = log["msg"].split('|')
                logged_in_username = msg_split[1]
                logged_in_user_id = msg_split[2]

            to_save.append(DeviceReportEntry(
                xform_id=xform_id,
                i=i,
                domain=domain,
                type=log["type"],
                msg=log["msg"],
                # must accept either date or datetime string
                date=dateutil.parser.parse(log["@date"]).replace(tzinfo=None),
                server_date=string_to_utc_datetime(doc_dict['received_on']),
                app_version=form.get('app_version'),
                device_id=form.get('device_id'),
                username=logged_in_username,
                user_id=logged_in_user_id,
            ))
        DeviceReportEntry.objects.bulk_create(to_save)
