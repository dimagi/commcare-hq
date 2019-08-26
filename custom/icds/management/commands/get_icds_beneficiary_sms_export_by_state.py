from couchexport.export import export_raw
from custom.icds.management.commands.get_icds_sms_export import BaseICDSSMSExportCommand
from custom.icds.const import (
    ANDHRA_PRADESH_SITE_CODE,
    BIHAR_SITE_CODE,
    CHHATTISGARH_SITE_CODE,
    JHARKHAND_SITE_CODE,
    MADHYA_PRADESH_SITE_CODE,
    RAJASTHAN_SITE_CODE,
)


class Command(BaseICDSSMSExportCommand):

    def get_state_abbreviation(self, state_code):
        return {
            ANDHRA_PRADESH_SITE_CODE: 'AP',
            BIHAR_SITE_CODE: 'BH',
            CHHATTISGARH_SITE_CODE: 'CG',
            JHARKHAND_SITE_CODE: 'JH',
            MADHYA_PRADESH_SITE_CODE: 'MP',
            RAJASTHAN_SITE_CODE: 'RJ',
        }[state_code]

    def get_export_name(self, state_code, start_date, end_date):
        start_date_fmt = start_date.strftime('%d.%m.%Y')
        end_date_fmt = end_date.strftime('%d.%m.%Y')
        return 'ICDS_CAS_SMS_%s_%s to %s' % (self.get_state_abbreviation(state_code), start_date_fmt, end_date_fmt)

    def handle(self, domain, start_date, end_date, **options):
        self.recipient_details = {}
        self.location_details = {}
        start_timestamp, end_timestamp = self.get_start_and_end_timestamps(start_date, end_date)

        headers = (
            'Date (IST)',
            'Phone Number',
            'Recipient Name',
            'State Name',
            'District Name',
            'Block Name',
            'LS Name',
            'AWC Name',
            'Text',
        )

        for state_code in (
            ANDHRA_PRADESH_SITE_CODE,
            BIHAR_SITE_CODE,
            CHHATTISGARH_SITE_CODE,
            JHARKHAND_SITE_CODE,
            MADHYA_PRADESH_SITE_CODE,
            RAJASTHAN_SITE_CODE,
        ):
            export_name = self.get_export_name(state_code, start_date, end_date)
            with open('%s.xlsx' % export_name, 'wb') as f:
                records = self.get_records(domain, start_timestamp, end_timestamp,
                    indicator_filter=['beneficiary_1', 'beneficiary_2'], state_filter=[state_code])

                data = tuple(record[:9] for record in records)

                export_raw(
                    ((export_name, headers), ),
                    ((export_name, data), ),
                    f
                )
