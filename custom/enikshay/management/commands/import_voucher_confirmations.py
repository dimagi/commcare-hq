import csv

from django.core.management.base import BaseCommand

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import get_person_case_from_voucher, CASE_TYPE_VOUCHER
from custom.enikshay.const import PERSON_FIRST_NAME, PERSON_LAST_NAME, VOUCHER_ID
from custom.enikshay.integrations.bets.repeater_generators import VoucherPayload
from custom.enikshay.integrations.bets.views import VoucherUpdate


class Command(BaseCommand):
    help = """
    import payment confirmations of vouchers paid offline
    """
    voucher_id_header = 'id'
    voucher_update_properties = [
        'status',
        'amount',
        'paymentDate',
        'comments',
        'failureDescription',
        'paymentMode',
        'checkNumber',
        'bankName',
        'eventType',
        'case_type',
    ]

    voucher_api_properties = [
        'VoucherID',
        'EventOccurDate',
        'EventID',
        'BeneficiaryUUID',
        'BeneficiaryType',
        'Location',
        'Amount',
        'DTOLocation',
        'InvestigationType',
        'PersonId',
        'AgencyId',
        'EnikshayApprover',
        'EnikshayRole',
        'EnikshayApprovalDate',
    ]

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('filename')
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )

    def handle(self, domain, filename, **options):
        self.domain = domain
        self.accessor = CaseAccessors(domain)
        commit = options['commit']

        with open(filename) as f:
            reader = csv.reader(f)
            headers = reader.next()
            missing_headers = set(self.voucher_update_properties) - set(headers)
            if missing_headers:
                print "Missing the following headers:"
                for header in missing_headers:
                    print " ", header
                print "\nAborting."
                return

            rows = [r for r in reader]

        print "Received info on {} vouchers.  Headers are:".format(len(rows) - 1)
        for header in headers:
            print header

        voucher_updates = []
        unrecognized_vouchers = []
        voucher_ids_to_update = set()

        for row in rows:
            voucher_id = row[headers.index(self.voucher_id_header)]
            voucher = self.all_vouchers_in_domain.get(voucher_id)
            if voucher:
                voucher_ids_to_update.add(voucher_id)
                voucher_updates.append(VoucherUpdate(
                    voucher=voucher,  # This property isn't defined on the model
                    id=voucher.case_id,
                    **{
                        prop: row[headers.index(prop)]
                        for prop in self.voucher_update_properties
                    }
                ))
            else:
                unrecognized_vouchers.append(row)

        self.log_voucher_updates(voucher_updates)
        self.log_unrecognized_vouchers(headers, unrecognized_vouchers)
        self.log_unmodified_vouchers(voucher_ids_to_update)

        if commit:
            self.commit_updates(voucher_updates)

    @property
    @memoized
    def all_vouchers_in_domain(self):
        voucher_ids = self.accessor.get_case_ids_in_domain(CASE_TYPE_VOUCHER)
        return {
            voucher.get_case_property(VOUCHER_ID): voucher
            for voucher in self.accessor.iter_cases(voucher_ids)
        }

    def write_csv(self, filename, headers, rows):
        filename = "voucher_confirmations-{}.csv".format(filename)
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

    def log_voucher_updates(self, voucher_updates):
        headers = ['ReadableID'] + self.voucher_api_properties + self.voucher_update_properties

        def make_row(voucher_update):
            api_payload = VoucherPayload.create_voucher_payload(voucher_update.voucher)
            return [voucher_update.voucher.get_case_property(VOUCHER_ID)] + [
                api_payload[prop] for prop in self.voucher_api_properties
            ] + [
                voucher_update[prop] for prop in self.voucher_update_properties
            ]

        rows = map(make_row, voucher_updates)
        self.write_csv('updates', headers, rows)

    def log_unrecognized_vouchers(self, headers, unrecognized_vouchers):
        self.write_csv('unrecognized', headers, unrecognized_vouchers)

    def log_unmodified_vouchers(self, voucher_ids_to_update):
        unmodified_vouchers = [
            voucher for voucher_id, voucher in self.all_vouchers_in_domain.items()
            if voucher_id not in voucher_ids_to_update
        ]

    def commit_updates(self, voucher_updates):
        pass
