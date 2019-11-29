"""
iterate phone numbers to find quality
"""
import csv
from copy import copy
from collections import defaultdict

result_group = {
    'count_less_than_10_digit': 0,
    'repeating_digits': 0,
    'starting_with_0': 0
}
result = defaultdict(dict)
test_state_names = ['Demo State',
 'Uttar Pradesh_GZB',
 'VL State',
 'Trial State',
 'Test State 2',
 'AWW  State Testing',
 'Practice Mode State',
 'Test State']


# run for pregnant

with open('phone_numbers_pregnant_mothers.csv') as _input:
    reader = csv.DictReader(_input)
    for row in reader:
        state_name = row['state_name']
        if state_name in test_state_names:
            continue
        if 'pregnant' not in result[state_name]:
            result[state_name]['pregnant'] = copy(result_group)
            result[state_name]['pregnant']['unique_valid_nums'] = set()
        num = row['Mobile Number']
        length = len(num)
        if length < 10:
            result[state_name]['pregnant']['count_less_than_10_digit'] += 1
        elif num == length * num[0]:
            result[state_name]['pregnant']['repeating_digits'] += 1
        elif num[0] == '0':
            result[state_name]['pregnant']['starting_with_0'] += 1
        else:
            result[state_name]['pregnant']['unique_valid_nums'].add(num)


# run for lactating
with open('phone_numbers_lactating_mothers.csv') as _input:
    reader = csv.DictReader(_input)
    for row in reader:
        state_name = row['state_name']
        if state_name in test_state_names:
            continue
        if 'lactating' not in result[state_name]:
            result[state_name]['lactating'] = copy(result_group)
            result[state_name]['lactating']['unique_valid_nums'] = set()
        num = row['Mobile Number']
        length = len(num)
        if length < 10:
            result[state_name]['lactating']['count_less_than_10_digit'] += 1
        elif num == length * num[0]:
            result[state_name]['lactating']['repeating_digits'] += 1
        elif num[0] == '0':
            result[state_name]['lactating']['starting_with_0'] += 1
        else:
            result[state_name]['lactating']['unique_valid_nums'].add(num)


# run for child
with open('phone_numbers_children.csv') as _input:
    reader = csv.DictReader(_input)
    for row in reader:
        state_name = row['state_name']
        if state_name in test_state_names:
            continue
        if 'children' not in result[state_name]:
            result[state_name]['children'] = copy(result_group)
            result[state_name]['children']['unique_valid_nums'] = set()
        num = row['Mobile Number']
        length = len(num)
        if length < 10:
            result[state_name]['children']['count_less_than_10_digit'] += 1
        elif num == length * num[0]:
            result[state_name]['children']['repeating_digits'] += 1
        elif num[0] == '0':
            result[state_name]['children']['starting_with_0'] += 1
        else:
            result[state_name]['children']['unique_valid_nums'].add(num)


with open('phone_numbers_consolidated.csv', 'w') as _output:
    writer = csv.writer(_output)
    writer.writerow([
        'state_name',
        'pregnant_count_less_than_10_digit',
        'pregnant_repeating_digits',
        'pregnant_starting_with_0',
        'pregnant_unique_valid_nums',
        'lactating_count_less_than_10_digit',
        'lactating_repeating_digits',
        'lactating_starting_with_0',
        'lactating_unique_valid_nums',
        'children_count_less_than_10_digit',
        'children_repeating_digits',
        'children_starting_with_0',
        'children_unique_valid_nums'
    ])
    for state_name in result:
        writer.writerow([
            state_name,
            result[state_name]['pregnant']['count_less_than_10_digit'],
            result[state_name]['pregnant']['repeating_digits'],
            result[state_name]['pregnant']['starting_with_0'],
            len(result[state_name]['pregnant']['unique_valid_nums']),
            result[state_name]['lactating']['count_less_than_10_digit'],
            result[state_name]['lactating']['repeating_digits'],
            result[state_name]['lactating']['starting_with_0'],
            len(result[state_name]['lactating']['unique_valid_nums']),
            result[state_name].get('children', {}).get('count_less_than_10_digit', 'N/A'),
            result[state_name].get('children', {}).get('repeating_digits', 'N/A'),
            result[state_name].get('children', {}).get('starting_with_0', 'N/A'),
            len(result[state_name].get('children', {}).get('unique_valid_nums', 'N/A')),
        ])
