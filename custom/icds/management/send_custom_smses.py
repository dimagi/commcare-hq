# send an sms to a list of phone numbers for particular states
# it needs custom/icds_reports/data_pull/awc_phone_numbers.py to be run first
# or some other file that provides the required details
import csv
import xlrd
from collections import defaultdict
from corehq.apps.sms.api import send_sms


STATE_NAMES = [
'Andaman & Nicobar Islands',
'Bihar',
'Chandigarh',
'Chhattisgarh',
'Dadra & Nagar Haveli',
'Daman & Diu',
'Delhi',
'Haryana',
'Himachal Pradesh',
'Jharkhand',
'Madhya Pradesh',
'Rajasthan',
'Uttar Pradesh',
'Uttarakhand'
]

content = "the sms to be sent"
file_path = "phone_number_list.xlsx"
# from the file
state_name_index = 7
number_index = 5

domain = "icds-cas"

wb = xlrd.open_workbook(file_path)
sheet = wb.sheet_by_index(0)

unique_phone_numbers_per_state = defaultdict(set)
for row_index in range(1, sheet.nrows):
    state_name = sheet.cell_value(row_index, state_name_index)
    if state_name in STATE_NAMES:
        # if phone number is read as float
        phone_num = str(sheet.cell_value(row_index, number_index)).split('.')[0]
        unique_phone_numbers_per_state[state_name].add(phone_num)

for state_name in unique_phone_numbers_per_state:
    print(state_name, len(unique_phone_numbers_per_state[state_name]))

response = input('send smses(YES to proceed)')
if response == "YES":
    with open("messages_sent.csv", "w") as _file:
        writer = csv.DictWriter(_file, fieldnames=['state_name', 'number', 'queued'])
        writer.writeheader()
        for state_name in unique_phone_numbers_per_state:
            print(state_name)
            if state_name != 'Daman & Diu':
                for phone_num in unique_phone_numbers_per_state[state_name]:
                    queued = send_sms(domain, None, phone_num, content)
                    writer.writerow({
                        'state_name': state_name,
                        'number': phone_num,
                        'queued': queued
                    })

