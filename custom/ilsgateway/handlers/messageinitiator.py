from datetime import datetime
from corehq.apps.sms.api import send_sms_to_verified_number
from dimagi.utils.dates import get_business_day_of_month_before
from corehq.apps.commtrack.models import CommTrackUser
from corehq.apps.locations.models import Location
from custom.ilsgateway.handlers import get_location
from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.reminders import TEST_HANDLER_HELP, TEST_HANDLER_BAD_CODE, SOH_HELP_MESSAGE, SUPERVISION_HELP, \
    SUPERVISION_REMINDER, SUBMITTED_NOTIFICATION_MSD, SUBMITTED_REMINDER_DISTRICT, SUBMITTED_REMINDER_FACILITY, \
    DELIVERY_REMINDER_FACILITY, DELIVERY_REMINDER_DISTRICT, DELIVERY_LATE_DISTRICT, TEST_HANDLER_CONFIRM, \
    REMINDER_MONTHLY_RANDR_SUMMARY, reports, REMINDER_MONTHLY_SOH_SUMMARY, REMINDER_MONTHLY_DELIVERY_SUMMARY, \
    SOH_THANK_YOU


class MessageInitiatior(KeywordHandler):

    def help(self):
        self.respond(TEST_HANDLER_HELP)

    def get_district_by_name(self, name):
        locs = Location.view('locations/by_name',
                             startkey=[self.domain, "DISTRICT", name],
                             endkey=[self.domain, "DISTRICT", name],
                             reduce=False,
                             include_docs=True)
        return locs

    def send_message(self, location, message, **kwargs):
        for user in CommTrackUser.by_domain(self.domain):
            dm = user.get_domain_membership(self.domain)
            if dm.location_id == location._id and user.get_verified_number():
                send_sms_to_verified_number(user.get_verified_number(), message % kwargs)

    def handle(self):
        if len(self.args) < 2:
            return self.help()

        command = self.args[0]
        rest = " ".join(self.args[1:])
        msd_code = self.args[1]
        fw_message = " ".join(self.args[2:])

        loc = get_location(self.domain, None, msd_code) or self.get_district_by_name(rest)
        if not loc['location']:
            self.respond(TEST_HANDLER_BAD_CODE, code=msd_code)
            return

        if command in ['soh', 'hmk']:
            self.send_message(loc['location'], SOH_HELP_MESSAGE)
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(supply_point=loc['case']._id,
                                             status_type=SupplyPointStatusTypes.SOH_FACILITY,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['supervision']:
            self.send_message(loc['location'], SUPERVISION_REMINDER)
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(supply_point=loc['case']._id,
                                             status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['randr']:
            if loc['location'].location_type == 'DISTRICT':
                self.send_message(loc['location'], SUBMITTED_REMINDER_DISTRICT)
                status_type = SupplyPointStatusTypes.R_AND_R_DISTRICT
            else:
                self.send_message(loc['location'], SUBMITTED_REMINDER_FACILITY)
                status_type = SupplyPointStatusTypes.R_AND_R_FACILITY
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(supply_point=loc['case']._id,
                                             status_type=status_type,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['delivery']:
            if loc['location'].location_type == 'DISTRICT':
                self.send_message(loc['location'], DELIVERY_REMINDER_DISTRICT)
                status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT
            else:
                self.send_message(loc['location'], DELIVERY_REMINDER_FACILITY)
                status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(supply_point=loc['case']._id,
                                             status_type=status_type,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['fw']:
            if fw_message:
                self.send_message(loc['location'], fw_message)
        elif command in ["latedelivery"]:
            self.send_message(loc['location'], DELIVERY_LATE_DISTRICT, group_name="changeme", group_total=1,
                              not_responded_count=2, not_received_count=3)
            self.respond(TEST_HANDLER_CONFIRM)
        elif command in ["randr_report"]:
            now = datetime.utcnow()
            self.respond(REMINDER_MONTHLY_RANDR_SUMMARY,
                         **reports.construct_summary(loc['case'],
                                                     SupplyPointStatusTypes.R_AND_R_FACILITY,
                                                     [SupplyPointStatusValues.SUBMITTED, SupplyPointStatusValues.NOT_SUBMITTED],
                                                     get_business_day_of_month_before(now.year, now.month, 5)))
        elif command in ["soh_report"]:
            now = datetime.utcnow()
            self.respond(REMINDER_MONTHLY_SOH_SUMMARY,
                         **reports.construct_summary(loc['case'],
                                                     SupplyPointStatusTypes.SOH_FACILITY,
                                                     [SupplyPointStatusValues.SUBMITTED],
                                                     get_business_day_of_month_before(now.year, now.month, -1)))
        elif command in ["delivery_report"]:
            now = datetime.utcnow()
            self.respond(REMINDER_MONTHLY_DELIVERY_SUMMARY,
                         **reports.construct_summary(loc['case'],
                                                     SupplyPointStatusTypes.DELIVERY_FACILITY,
                                                     [SupplyPointStatusValues.RECEIVED,
                                                     SupplyPointStatusValues.NOT_RECEIVED],
                                                     get_business_day_of_month_before(now.year, now.month, 15)))
        elif command in ["soh_thank_you"]:
            self.respond(SOH_THANK_YOU)