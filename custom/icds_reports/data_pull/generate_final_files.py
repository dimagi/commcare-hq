import csv
from copy import copy

# Home visits

columns = [
    'state_name',
    'district_name',
    'block_name',
    'supervisor_name',
    'awc_name',
    'expected_visits',
    'valid_visits',
]

output_columns = [
    'State',
    'District',
    'Block',
    'Sector',
    'AWC',
    'Periodicity',
    'Number of home visits planned as per home visit planner',
    'Number of home visits undertaken',
]

file_name = "home_visits_nov.csv"

writers = {}
open_files = []
with open(file_name) as _file:
    reader = csv.DictReader(_file)
    for row in reader:
        state_name = row['state_name']
        if state_name in writers:
            writer = writers[state_name]
        else:
            f = open("data_pull/home_visits/home_visits_nov_%s.csv" % state_name, "w")
            open_files.append(f)
            writer = csv.DictWriter(f, fieldnames=output_columns)
            writer.writeheader()
            writers[state_name] = writer
        writer.writerow({
            'State': row['state_name'],
            'District': row['district_name'],
            'Block': row['block_name'],
            'Sector': row['supervisor_name'],
            'AWC': row['awc_name'],
            'Periodicity': 'Month',
            'Number of home visits planned as per home visit planner': row['expected_visits'],
            'Number of home visits undertaken': row['valid_visits']
        })

for open_file in open_files:
    open_file.close()




# VHSND

columns = [
    'state_name',
    'district_name',
    'block_name',
    'supervisor_name',
    'awc_name',
    'month',
    'vhsnd_conducted',
    'vhsnd_date_past_month',
    'child_immu',
    'anc_today',
    'vhnd_gmp'
]

output_columns = [
'State',
'District',
'Block',
'Sector',
'Month',
'AWC',
'VHSND conducted',
'Date of VHSND conducted',
'Any children immunized during the event',
'Any women for whom ANC conducted',
'Any Children weighed during VHSND'
]

file_name = "vhnd_november.csv"

writers = {}
open_files = []
with open(file_name) as _file:
    reader = csv.DictReader(_file)
    for row in reader:
        state_name = row['state_name']
        if state_name in writers:
            writer = writers[state_name]
        else:
            f = open("data_pull/vhsnd/vhsnd_nov_%s.csv" % state_name, "w")
            open_files.append(f)
            writer = csv.DictWriter(f, fieldnames=output_columns)
            writer.writeheader()
            writers[state_name] = writer
        writer.writerow({
            'State': row['state_name'],
            'District': row['district_name'],
            'Block': row['block_name'],
            'Sector': row['supervisor_name'],
            'Month': row['month'],
            'AWC': row['awc_name'],
            'VHSND conducted': row['vhsnd_conducted'],
            'Date of VHSND conducted': row['vhsnd_date_past_month'],
            'Any children immunized during the event': row['child_immu'],
            'Any women for whom ANC conducted': row['anc_today'],
            'Any Children weighed during VHSND': row['vhnd_gmp']
        })

for open_file in open_files:
    open_file.close()

# Beneficiary coverage

"""
create unlogged table temp_child_data_pull_nov as select
awc_id,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_in_month else 0 END) as nov_open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_in_month else 0 END) as nov_open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_all_registered_in_month else 0 END) as nov_open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_all_registered_in_month else 0 END) as nov_open_register_till_month_3_6
from "child_health_monthly" child_health where month='2019-11-01'
group by awc_id;

COPY(select
state_name,
district_name,
block_name,
supervisor_name,
awc_name,
sum(nov_open_valid_till_month_0_3) as "nov_open_valid_till_month_0_3",
sum(nov_open_valid_till_month_3_6) as "nov_open_valid_till_month_3_6",
sum(nov_open_register_till_month_0_3) as "nov_open_register_till_month_0_3",
sum(nov_open_register_till_month_3_6) as "nov_open_register_till_month_3_6"
from temp_child_data_pull_nov t join awc_location_local a on a.doc_id=t.awc_id where aggregation_level=5 and state_is_test=0
group by state_name,
district_name,
block_name,
supervisor_name,
awc_name
order by state_name asc
) to '/tmp/beneficiary_coverage_child_nov.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';



create unlogged table temp_child_data_pull_oct as select
awc_id,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_in_month else 0 END) as oct_open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_in_month else 0 END) as oct_open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 THEN valid_all_registered_in_month else 0 END) as oct_open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 THEN valid_all_registered_in_month else 0 END) as oct_open_register_till_month_3_6
from "child_health_monthly" child_health where month='2019-10-01'
group by awc_id;

COPY(select
state_name,
district_name,
block_name,
supervisor_name,
awc_name,
sum(oct_open_valid_till_month_0_3) as "oct_open_valid_till_month_0_3",
sum(oct_open_valid_till_month_3_6) as "oct_open_valid_till_month_3_6",
sum(oct_open_register_till_month_0_3) as "oct_open_register_till_month_0_3",
sum(oct_open_register_till_month_3_6) as "oct_open_register_till_month_3_6"
from temp_child_data_pull_oct t join awc_location_local a on a.doc_id=t.awc_id where aggregation_level=5 and state_is_test=0
group by state_name,
district_name,
block_name,
supervisor_name,
awc_name
order by state_name asc
) to '/tmp/beneficiary_coverage_child_oct.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

DROP TABLE IF EXISTS temp_child_data_pull_oct;
DROP TABLE IF EXISTS temp_child_data_pull_nov;


COPY(
select
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    cases_ccs_pregnant_all as nov_open_pw_registered_till_month,
    cases_ccs_lactating_all as nov_open_lw_registered_till_month,
    cases_ccs_lactating as nov_open_lw_valid_till_month,
    cases_ccs_pregnant as nov_open_lw_valid_till_month
FROM agg_awc_monthly
where agg_awc_monthly.num_launched_awcs=1 and agg_awc_monthly.month='2019-11-01' and agg_awc_monthly.aggregation_level=5
) TO '/tmp/beneficiary_coverage_mother_nov_new.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

COPY(
select
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    cases_ccs_pregnant_all as oct_open_pw_registered_till_month,
    cases_ccs_lactating_all as oct_open_lw_registered_till_month,
    cases_ccs_lactating as oct_open_lw_valid_till_month,
    cases_ccs_pregnant as oct_open_lw_valid_till_month
FROM agg_awc_monthly
where agg_awc_monthly.num_launched_awcs=1 and agg_awc_monthly.month='2019-10-01' and agg_awc_monthly.aggregation_level=5
) TO '/tmp/beneficiary_coverage_mother_oct_new.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';


create unlogged table temp_child_data_pull_oct as select
awc_id,
    SUM(CASE WHEN age_tranche::INTEGER<=36 and sex='F' THEN valid_in_month else 0 END) as oct_F_open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 and sex='F' THEN valid_in_month else 0 END) as oct_F_open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 and sex='F' THEN valid_all_registered_in_month else 0 END) as oct_F_open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 and sex='F' THEN valid_all_registered_in_month else 0 END) as oct_F_open_register_till_month_3_6,

    SUM(CASE WHEN age_tranche::INTEGER<=36 and sex='M' THEN valid_in_month else 0 END) as oct_M_open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 and sex='M' THEN valid_in_month else 0 END) as oct_M_open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 and sex='M' THEN valid_all_registered_in_month else 0 END) as oct_M_open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 and sex='M' THEN valid_all_registered_in_month else 0 END) as oct_M_open_register_till_month_3_6


from "child_health_monthly" child_health where month='2019-10-01'
group by awc_id;

COPY(select
state_name,
district_name,
block_name,
supervisor_name,
awc_name,
sum(F_open_valid_till_month_0_3) as "oct_F_open_valid_till_month_0_3",
sum(F_open_valid_till_month_3_6) as "oct_F_open_valid_till_month_3_6",
sum(F_open_register_till_month_0_3) as "oct_F_open_register_till_month_0_3",
sum(F_open_register_till_month_3_6)as "oct_F_open_register_till_month_3_6",

sum(M_open_valid_till_month_0_3) as "oct_M_open_valid_till_month_0_3",
sum(M_open_valid_till_month_3_6) as "oct_M_open_valid_till_month_3_6",
sum(M_open_register_till_month_0_3) as "oct_M_open_register_till_month_0_3",
sum(M_open_register_till_month_3_6)as "oct_M_open_register_till_month_3_6"
from agg_awc_monthly left join
    temp_child_data_pull_oct t on agg_awc_monthly.awc_id=t.awc_id
where aggregation_level=5 and agg_awc_monthly.month='2019-11-01' and num_launched_awcs=1
group by state_name,
district_name,
block_name,
supervisor_name,
awc_name
order by state_name asc
) to '/tmp/child_oct_new.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

create unlogged table temp_child_data_pull_nov as select
awc_id,
    SUM(CASE WHEN age_tranche::INTEGER<=36 and sex='F' THEN valid_in_month else 0 END) as nov_F_open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 and sex='F' THEN valid_in_month else 0 END) as nov_F_open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 and sex='F' THEN valid_all_registered_in_month else 0 END) as nov_F_open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 and sex='F' THEN valid_all_registered_in_month else 0 END) as nov_F_open_register_till_month_3_6,

    SUM(CASE WHEN age_tranche::INTEGER<=36 and sex='M' THEN valid_in_month else 0 END) as nov_M_open_valid_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 and sex='M' THEN valid_in_month else 0 END) as nov_M_open_valid_till_month_3_6,
    SUM(CASE WHEN age_tranche::INTEGER<=36 and sex='M' THEN valid_all_registered_in_month else 0 END) as nov_M_open_register_till_month_0_3,
    SUM(CASE WHEN age_tranche::INTEGER between 37 and 72 and sex='M' THEN valid_all_registered_in_month else 0 END) as nov_M_open_register_till_month_3_6


from "child_health_monthly" child_health where month='2019-11-01'
group by awc_id;

COPY(select
state_name,
district_name,
block_name,
supervisor_name,
awc_name,
sum(nov_F_open_valid_till_month_0_3) as "nov_F_open_valid_till_month_0_3",
sum(nov_F_open_valid_till_month_3_6) as "nov_F_open_valid_till_month_3_6",
sum(nov_F_open_register_till_month_0_3) as "nov_F_open_register_till_month_0_3",
sum(nov_F_open_register_till_month_3_6)as "nov_F_open_register_till_month_3_6",

sum(nov_M_open_valid_till_month_0_3) as "nov_M_open_valid_till_month_0_3",
sum(nov_M_open_valid_till_month_3_6) as "nov_M_open_valid_till_month_3_6",
sum(nov_M_open_register_till_month_0_3) as "nov_M_open_register_till_month_0_3",
sum(nov_M_open_register_till_month_3_6)as "nov_M_open_register_till_month_3_6"
from agg_awc_monthly left join
    temp_child_data_pull_nov t on agg_awc_monthly.awc_id=t.awc_id
where aggregation_level=5 and agg_awc_monthly.month='2019-11-01' and num_launched_awcs=1
group by state_name,
district_name,
block_name,
supervisor_name,
awc_name
order by state_name asc
) to '/tmp/child_nov_new.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';

"""

child_file_name_1 = "child_oct_new.csv"
child_file_name_2 = "child_nov_new.csv"

open_files = []

child_file_1 = open(child_file_name_1)
open_files.append(child_file_1)
child_file_2 = open(child_file_name_2)
open_files.append(child_file_2)

reader1 = csv.DictReader(child_file_1)
headers1 = reader1.fieldnames
reader2 = csv.DictReader(child_file_2)
headers2 = reader2.fieldnames

all_headers = copy(reader2.fieldnames)
new_headers = []
for header in reader1.fieldnames:
    if header not in all_headers:
        all_headers.append(header)
        new_headers.append(header)

first_set_of_data = {}
second_set_of_data = {}

for row in reader1:
    if row['awc_name'] in first_set_of_data:
        print("duplicate found for %s" % row['awc_name'])
    first_set_of_data[row['awc_name']] = row

for row in reader2:
    awc_name = row['awc_name']
    if awc_name in second_set_of_data:
        print("duplicate found for %s" % awc_name)
    second_set_of_data[awc_name] = row
    other_details = first_set_of_data.get(awc_name, {})
    for header in new_headers:
        second_set_of_data[awc_name][header] = other_details.get(header, 'NA')

for _file in open_files:
    _file.close()

with open("data_pull/beneficiary_coverage/beneficiary_coverage_child_new.csv", "w") as _file:
    writer = csv.DictWriter(_file, fieldnames=all_headers)
    writer.writeheader()
    for row in second_set_of_data.values():
        writer.writerow(row)


# mother

mother_file_name_1 = "beneficiary_coverage_mother_oct_new.csv"
mother_file_name_2 = "beneficiary_coverage_mother_nov_new.csv"

open_files = []

mother_file_1 = open(mother_file_name_1)
open_files.append(mother_file_1)
mother_file_2 = open(mother_file_name_2)
open_files.append(mother_file_2)

reader1 = csv.DictReader(mother_file_1)
headers1 = reader1.fieldnames
reader2 = csv.DictReader(mother_file_2)
headers2 = reader2.fieldnames

all_headers = copy(reader2.fieldnames)
new_headers = []
for header in reader1.fieldnames:
    if header not in all_headers:
        all_headers.append(header)
        new_headers.append(header)

first_set_of_data = {}
second_set_of_data = {}

for row in reader1:
    if row['awc_name'] in first_set_of_data:
        print("duplicate found for %s" % row['awc_name'])
    first_set_of_data[row['awc_name']] = row

for row in reader2:
    awc_name = row['awc_name']
    if awc_name in second_set_of_data:
        print("duplicate found for %s" % awc_name)
    second_set_of_data[awc_name] = row
    other_details = first_set_of_data.get(awc_name, {})
    for header in new_headers:
        second_set_of_data[awc_name][header] = other_details.get(header, 'NA')

for _file in open_files:
    _file.close()

with open("data_pull/beneficiary_coverage/beneficiary_coverage_mother_new.csv", "w") as _file:
    writer = csv.DictWriter(_file, fieldnames=all_headers)
    writer.writeheader()
    for row in second_set_of_data.values():
        writer.writerow(row)

