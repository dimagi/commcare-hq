import hashlib
from django.db import IntegrityError
from pillowtop.listener import BasicPillow
from couchforms.models import XFormInstance
from phonelog.models import UserLog, Log
import dateutil.parser as dparser

def force_list(obj_or_list):
    return obj_or_list if isinstance(obj_or_list, list) else [obj_or_list]

def get_logs(form, report_name, report_slug):
    report = form.get(report_name, {}) or {}
    if isinstance(report, list):
        return filter(None, [log.get(report_slug) for log in report])
    return report.get(report_slug, [])

class PhoneLogPillow(BasicPillow):
    document_class = XFormInstance
    couch_filter = 'phonelog/all_logs'

    def change_transport(self, doc_dict):
        xform_id = doc_dict.get('_id')
        form = doc_dict.get('form', {})
        userlogs = get_logs(form, 'user_subreport', 'user')
        for log in force_list(userlogs):
            u = UserLog(user_id=log["user_id"], username=log["username"],
                        sync_token=log["sync_token"], xform_id=xform_id)
            u.save()

        domain = doc_dict.get('domain')
        logs = get_logs(form, 'log_subreport', 'log')
        logged_in_user = 'unknown'
        for log in filter(None, force_list(logs)):
            if log["type"] == 'login':
                logged_in_user = log["msg"].split('-')[1]

            uuid = hashlib.md5(log["type"] + log["@date"]).hexdigest()
            try:
                l, _ = Log.objects.get_or_create(id=uuid, xform_id=xform_id, domain=domain,
                                         type=log["type"], msg=log["msg"],
                                         date=dparser.parse(log["@date"]),
                                         app_version=form.get('app_version'),
                                         device_id=form.get('device_id'),
                                         username=logged_in_user)
            except IntegrityError:
                pass
