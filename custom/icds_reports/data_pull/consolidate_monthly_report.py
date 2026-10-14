import csv
from copy import copy
from collections import defaultdict

STATE_NAME_COLUMN = "state_name"
filenames = [
    'monthly_stats1.csv',
    'monthly_stats2.csv',
    'monthly_stats3.csv',
    'monthly_stats4.csv',
    'monthly_stats5.csv',
    'monthly_stats6.csv',
    'monthly_stats7.csv',
    'monthly_stats8.csv',
    'monthly_stats9.csv',
    'monthly_stats10.csv',
    'monthly_stats11.csv',
    'monthly_stats12.csv'
]

test_state_names = [
    'Demo State',
    'Uttar Pradesh_GZB',
    'VL State',
    'Trial State',
    'Test State 2',
    'AWW  State Testing',
    'Practice Mode State',
    'Test State'
]

result = defaultdict(dict)
"""
iterate each file
use the column name which is STATE_NAME_COLUMN as the key in result
and then add all other columns to state name dict
"""
for filename in filenames:
    with open(filename) as _file:
        reader = csv.DictReader(_file)
        for row in reader:
            state_name = row[STATE_NAME_COLUMN]
            if state_name in test_state_names:
                continue
            for column_name, value in row.items():
                if column_name != STATE_NAME_COLUMN:
                    result[state_name][column_name] = value

headers = list(list(result.values())[0].keys())
with open("Consolidated_monthly_report.csv", "w") as _file:
    fieldnames = ['State'] + headers
    writer = csv.DictWriter(_file, fieldnames)
    writer.writeheader()
    for state_name, col_values in result.items():
        row = copy(col_values)
        row['State'] = state_name
        writer.writerow(row)
