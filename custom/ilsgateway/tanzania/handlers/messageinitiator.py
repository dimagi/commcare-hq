from datetime import datetime, timedelta
from corehq.apps.locations.dbaccessors import get_users_by_location_id

from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.util.translation import localize
from dimagi.utils.dates import get_business_day_of_month_before
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import TEST_HANDLER_HELP, TEST_HANDLER_BAD_CODE, SOH_HELP_MESSAGE, \
    SUPERVISION_REMINDER, SUBMITTED_REMINDER_DISTRICT, SUBMITTED_REMINDER_FACILITY, \
    DELIVERY_REMINDER_FACILITY, DELIVERY_REMINDER_DISTRICT, DELIVERY_LATE_DISTRICT, TEST_HANDLER_CONFIRM, \
    REMINDER_MONTHLY_RANDR_SUMMARY, reports, REMINDER_MONTHLY_SOH_SUMMARY, REMINDER_MONTHLY_DELIVERY_SUMMARY, \
    SOH_THANK_YOU, LOSS_ADJUST_HELP


class MessageInitiatior(KeywordHandler):

    def help(self):
        self.respond(TEST_HANDLER_HELP)
        return True

    def get_district_by_name(self, name):
        try:
            return SQLLocation.objects.get(domain=self.domain, name=name)
        except SQLLocation.DoesNotExist:
            return None

    def send_message(self, sql_location, message, **kwargs):
        for user in get_users_by_location_id(self.domain, sql_location.location_id):
            verified_number = user.get_verified_number()
            if verified_number:
                with localize(user.get_language_code()):
                    send_sms_to_verified_number(verified_number, message % kwargs)

    def handle(self):
        if len(self.args) < 2:
            return self.help()

        command = self.args[0]
        rest = " ".join(self.args[1:])
        msd_code = self.args[1].lower()
        fw_message = " ".join(self.args[2:])

        try:
            sql_location = SQLLocation.objects.get(domain=self.domain, site_code__iexact=msd_code)
        except SQLLocation.DoesNotExist:
            sql_location = self.get_district_by_name(rest)

        if not sql_location:
            self.respond(TEST_HANDLER_BAD_CODE, code=msd_code)
            return True

        if command in ['soh', 'hmk']:
            self.send_message(sql_location, SOH_HELP_MESSAGE)
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(location_id=sql_location.location_id,
                                             status_type=SupplyPointStatusTypes.SOH_FACILITY,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['la']:
            self.send_message(sql_location, LOSS_ADJUST_HELP)
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(location_id=sql_location.location_id,
                                             status_type=SupplyPointStatusTypes.LOSS_ADJUSTMENT_FACILITY,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['supervision']:
            self.send_message(sql_location, SUPERVISION_REMINDER)
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(location_id=sql_location.location_id,
                                             status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['randr']:
            if sql_location.location_type.name == 'DISTRICT':
                self.send_message(sql_location, SUBMITTED_REMINDER_DISTRICT)
                status_type = SupplyPointStatusTypes.R_AND_R_DISTRICT
            else:
                self.send_message(sql_location, SUBMITTED_REMINDER_FACILITY)
                status_type = SupplyPointStatusTypes.R_AND_R_FACILITY
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(location_id=sql_location.location_id,
                                             status_type=status_type,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['delivery']:
            if sql_location.location_type.name == 'DISTRICT':
                self.send_message(sql_location, DELIVERY_REMINDER_DISTRICT)
                status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT
            else:
                self.send_message(sql_location, DELIVERY_REMINDER_FACILITY)
                status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
            now = datetime.utcnow()
            SupplyPointStatus.objects.create(location_id=sql_location.location_id,
                                             status_type=status_type,
                                             status_value=SupplyPointStatusValues.REMINDER_SENT,
                                             status_date=now)
        elif command in ['fw']:
            if fw_message:
                self.send_message(sql_location, fw_message)
        elif command in ["latedelivery"]:
            self.send_message(sql_location, DELIVERY_LATE_DISTRICT, group_name="changeme", group_total=1,
                              not_responded_count=2, not_received_count=3)
        elif command in ["randr_report"]:
            now = datetime.utcnow()
            self.respond(REMINDER_MONTHLY_RANDR_SUMMARY, **reports.construct_summary(
                sql_location.couch_location,
                SupplyPointStatusTypes.R_AND_R_FACILITY,
                [SupplyPointStatusValues.SUBMITTED, SupplyPointStatusValues.NOT_SUBMITTED],
                get_business_day_of_month_before(now.year, now.month, 5)
            ))
        elif command in ["soh_report"]:
            now = datetime.utcnow()
            last_month = datetime(now.year, now.month, 1) - timedelta(days=1)
            self.respond(
                REMINDER_MONTHLY_SOH_SUMMARY,
                **reports.construct_summary(
                    sql_location.couch_location,
                    SupplyPointStatusTypes.SOH_FACILITY,
                    [SupplyPointStatusValues.SUBMITTED],
                    get_business_day_of_month_before(last_month.year, last_month.month, -1)
                )
            )
        elif command in ["delivery_report"]:
            now = datetime.utcnow()
            self.respond(REMINDER_MONTHLY_DELIVERY_SUMMARY,
                         **reports.construct_summary(sql_location.couch_location,
                                                     SupplyPointStatusTypes.DELIVERY_FACILITY,
                                                     [SupplyPointStatusValues.RECEIVED,
                                                     SupplyPointStatusValues.NOT_RECEIVED],
                                                     get_business_day_of_month_before(now.year, now.month, 15)))
        elif command in ["soh_thank_you"]:
            self.send_message(sql_location, SOH_THANK_YOU)

        self.respond(TEST_HANDLER_CONFIRM)
        return True
