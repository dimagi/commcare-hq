from corehq.apps.reports.custom import HQReport
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.models import MessageLog, SMSLog, CallLog, EventLog, INCOMING, OUTGOING, MISSED_EXPECTED_CALLBACK
from corehq.apps.reminders.models import CaseReminderHandler
from datetime import datetime, timedelta



class MissedCallbackReport(HQReport):
    name = "Missed Callbacks"
    slug = "missed_callbacks"
    description = "Summarizes two weeks of SMS and Callback interactions for all patients."
    template_name = "a5288/missed-callbacks.html"

    def calc(self):
        self.context["report_data"] = self.get_missed_callback_report_context(self.domain)
    
    # site_list should be None for all sites, or a list of sites to filter on
    def get_missed_callback_report_context(self, domain, site_list=None, end_date=None):
        date_list = []
        if end_date is None:
            end_date = datetime.utcnow().date()
        for day_num in range(-13, 1):
            date_list.append(str(end_date + timedelta(days = day_num)))
        data = {}
        for case in CommCareCase.view("hqcase/types_by_domain", startkey=[domain, "patient"], endkey=[domain, "patient"], reduce=False, include_docs=True).all():
            site = case.get_case_property("site")
            if((site_list is None) or (site in site_list)):
                entry = {"dates" : []}
                for date in date_list:
                    entry["dates"].append({"sms_count" : 0, "call_count" : 0, "missed_callback_count" : 0})
                entry["recipient"] = case
                data[case._id] = entry
        for sms in SMSLog.by_domain_date(domain).all():
            if sms.direction == OUTGOING and sms.couch_recipient_doc_type == "CommCareCase" and sms.couch_recipient in data:
                entry = data[sms.couch_recipient]
                date = str(CaseReminderHandler.utc_to_local(entry["recipient"], sms.date).date())
                if date in date_list:
                    entry["dates"][date_list.index(date)]["sms_count"] += 1
        for call in CallLog.by_domain_date(domain).all():
            if call.direction == INCOMING and call.couch_recipient_doc_type == "CommCareCase" and call.couch_recipient in data:
                entry = data[call.couch_recipient]
                date = str(CaseReminderHandler.utc_to_local(entry["recipient"], call.date).date())
                if date in date_list:
                    entry["dates"][date_list.index(date)]["call_count"] += 1
        for event in EventLog.view("sms/event_by_domain_date_recipient", startkey=[domain], endkey=[domain, {}], include_docs=True).all():
            if event.event_type == MISSED_EXPECTED_CALLBACK and event.couch_recipient_doc_type == "CommCareCase" and event.couch_recipient in data:
                entry = data[event.couch_recipient]
                date = str(CaseReminderHandler.utc_to_local(entry["recipient"], event.date).date())
                if date in date_list:
                    entry["dates"][date_list.index(date)]["missed_callback_count"] += 1
        
        # Calculate final outcome for each person, for each day
        for case_id, entry in data.items():
            total_ok = 0
            total_no_response = 0
            total_not_sent = 0
            total_pending = 0
            for date in entry["dates"]:
                ok = False
                no_response = False
                not_sent = False
                pending = False
                if date["sms_count"] == 0:
                    not_sent = True
                    total_not_sent += 1
                elif date["call_count"] > 0 and date["missed_callback_count"] == 0:
                    ok = True
                    total_ok += 1
                elif date["missed_callback_count"] > 0:
                    no_response = True
                    total_no_response += 1
                else:
                    pending = True
                    total_pending += 1
                date["ok"] = ok
                date["no_response"] = no_response
                date["not_sent"] = not_sent
                date["pending"] = pending
            entry["total_ok"] = total_ok
            entry["total_no_response"] = total_no_response
            entry["total_not_sent"] = total_not_sent
            entry["total_pending"] = total_pending
        
        context = {
            "date_list" : date_list,
            "data" : data
        }
        return context



