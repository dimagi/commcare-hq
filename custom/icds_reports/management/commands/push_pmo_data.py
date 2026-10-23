from django.core.management.base import BaseCommand
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil import parser
from custom.icds_reports.models.views import PMOAPIView
import hashlib
from base64 import b64encode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests


class Command(BaseCommand):
    help = "Update the SQL output files for ICDS Aggregation helpers"

    # TODO: These following statics will be updated as NIC gives us the details
    STATIC_PROJECT_DATA = {
        'mcode': 0,
        'teh_code': 0,
        'blk_code': 0,
        'sector_code': 0,
        'gp_code': 0,
        'vill_code': 0,
        'dept_code': 0,
        'project_code': 0,
        'dataportmode': 1,
        'modedesc': 0,
        'data_lvl_code': 4,

    }

    def handle(self, encryption_key, date_range_api, data_push_api, *args, **options):
        missing_months = self.get_missing_months()
        self.encryption_key = encryption_key.encode()
        self.date_range_api = date_range_api
        self.data_push_api = data_push_api

        for month in missing_months:
            print(f"Sending data for month: {month}")
            self.send_data(self.get_month_data(month))

    def get_missing_months(self):
        data = {
            'mcode': self.STATIC_PROJECT_DATA['mcode'],
            'state_code': 999,
            'dept_code': self.STATIC_PROJECT_DATA['dept_code'],
            'project_code': self.STATIC_PROJECT_DATA['project_code'],
            'sec_code': 0  # TODO: Will be updated as NIC gives us this
        }

        headers = {'Content-Type': "application/json"}

        response = requests.post(self.date_range_api, data=data, headers=headers)
        if response.status_code ==200:
            json_content = json.loads(response.content)
            dates_list = json_content['RetDMDashCaption']
            return [parser.parse(missing_date['DATE_DD_MM_YYYY']).date().replace(day=1)
                    for missing_date in dates_list]
        else:
            print("Error while fetching the dates")
            print(response.content)
            return []

    def get_string_hash(self, string):
        hash_obj = hashlib.md5(string.encode())
        return hash_obj.hexdigest()

    def get_month_data(self, month):
        pmo_data_query = PMOAPIView.objects.filter(month=month).values(
            'state_site_code',
            'district_site_code',
            'num_launched_awcs',
            'bf_at_birth',
            'born_in_month',
            'cf_initiation_in_month',
            'cf_initiation_eligible',
            'wer_weighed',
            'wer_eligible',
            'cbe_conducted',
            'vhnd_conducted',
            'month'
        )
        pmo_month_payload = []
        for data in pmo_data_query:
            pmo_month_payload.append(self.get_encrypted_record(data))

        return pmo_month_payload

    def get_encrypted_record(self, data):
        packet = dict()
        packet.update(self.STATIC_PROJECT_DATA)
        packet['state_code'] = data['state_site_code']
        packet['district_code'] = data['district_site_code'][2:]
        packet['cnt1'] = int(data['num_launched_awcs'])
        packet['cnt2'] = round(data['bf_at_birth'] / float(data['born_in_month']), 5)
        packet['cnt3'] = round(data['cf_initiation_in_month'] / float(data['cf_initiation_eligible']), 5)
        packet['cnt4'] = round(data['wer_weighed'] / float(data['wer_eligible']), 5)
        packet['cnt5'] = int(data['cbe_conducted'])
        packet['cnt6'] = int(data['vhnd_conducted'])
        packet['yr'] = data['month'].year
        packet['mnth'] = data['month'].month
        packet['datadt'] = (data['month'] + relativedelta(months=1, seconds=-1)).strftime('%m/%d/%Y')  # month end
        packet_string = json.dumps(packet)
        return self.encrypt_string(packet_string)

    def encrypt_string(self, input_string):
        input_string += f"|dt={datetime.now()}"
        input_string += f"|checksum={self.get_string_hash(input_string)}"
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv=self.encryption_key)
        input_string_bytes = input_string.encode()
        ct_bytes = cipher.encrypt(pad(input_string_bytes, 16))
        return b64encode(ct_bytes).decode('utf-8')

    def send_data(self, missing_data_list):
        data_payload = {
            'IP': {
                "mcode": 0,  # TODO: Will be updated as NIC gives us this
                "state_code": 999,
                "dept_code": self.STATIC_PROJECT_DATA['dept_code'],
                "project_code": self.STATIC_PROJECT_DATA['project_code'],
                "sec_code": self.STATIC_PROJECT_DATA['sector_code']
            },
            "Records": missing_data_list
        }
        headers = {'Content-Type': "application/json"}
        response = requests.post(self.data_push_api, data=data_payload, headers=headers)
        try:
            json_content = json.loads(response.content)
            print(json_content['Status'])
            print(json_content['Message'])

        except json.decoder.JSONDecodeError:
            print(response.status_code)
            print(response.content)

    def add_arguments(self, parser):
        parser.add_argument('encryption_key',
                            help="Encryption key with which data has to be encrypted.",)
        parser.add_argument('date_range_api',
                            help="API URL to fetch the pendency",)
        parser.add_argument('data_push_api',
                            help="API URL to push the data",)
