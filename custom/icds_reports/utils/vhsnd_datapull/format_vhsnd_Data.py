import csv
import openpyxl
from django.utils.dateparse import parse_date
from collections import defaultdict
import datetime, calendar

consolidated_data = defaultdict(dict)

YEAR = 2020
MONTH = 2
num_days = calendar.monthrange(YEAR, MONTH)[1]
days = [datetime.date(YEAR, MONTH, day) for day in range(1, num_days+1)]

dates = [day.strftime('%d/%m/%Y') for day in days]

headers = ['State', 'District', 'Block', 'Sector', 'AWC']
headers.extend(dates)
headers.append('Grand Total')

filename = "vhsnd_data_pull_feb.csv"
with open(filename) as _input:
    reader = csv.DictReader(_input)
    for row in reader:
        state_name = row['state_name']
        data_key = (row['state_name'], row['district_name'], row['block_name'], row['supervisor_name'], row['awc_name'])
        vhsnd_date = parse_date(row['vhsnd_date_past_month'])
        vhsnd_date = vhsnd_date.strftime('%d/%m/%Y')
        if data_key in consolidated_data[state_name]:
            consolidated_data[state_name][data_key].append(vhsnd_date)
        else:
            consolidated_data[state_name][data_key] = [vhsnd_date]

# consolidate in an excel file
wb = openpyxl.Workbook(write_only=True)
for state_name, all_details in consolidated_data.items():
    ws = wb.create_sheet(title=state_name)
    ws.append(headers)
    for details, vhsnd_dates in all_details.items():
        awc_row = [details[0], details[1], details[2], details[3], details[4]]
        for a_date in dates:
            if a_date in vhsnd_dates:
                awc_row.append(1)
            else:
                awc_row.append('')
        awc_row.append(len(vhsnd_dates))
        ws.append(awc_row)
wb.save("VHSND_Feb_Consolidated.xlsx")
