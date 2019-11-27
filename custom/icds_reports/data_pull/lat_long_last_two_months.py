from copy import copy
import csv

from corehq.apps.locations.models import SQLLocation

"""
COPY(
SELECT awc_id, awc_name, state_name
FROM agg_awc_monthly
WHERE month='2019-11-01' AND num_launched_awcs=1 AND aggregation_level=5
) TO '/tmp/awc_id_name_launched_nov.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
"""
awc_id_name_mapping_file = "awc_id_name_launched_nov.csv"

"""
COPY(
SELECT DISTINCT ON (awc_id) awc_id, form_location_lat, form_location_long
FROM "ucr_icds-cas_static-daily_feeding_forms_85b1167f"
WHERE submitted_on >= '2019-10-01' AND form_location_lat IS NOT NULL ORDER BY awc_id, submitted_on DESC
) TO '/tmp/lat_long.csv' DELIMITER ',' CSV HEADER ENCODING 'UTF-8';
"""
lat_long_file = "lat_long.csv"

missing_awc_ids = []
awc_id_name_mapping = {}
skipped_test_location_data = 0
unexpected_state_names = []

# extracted from ICDS using is_test_location metadata on locations
test_location_names = ['Demo State',
 'Uttar Pradesh_GZB',
 'VL State',
 'Trial State',
 'Test State 2',
 'AWW  State Testing',
 'Practice Mode State',
 'Test State']

real_location_names = ['Uttar Pradesh',
  'Chhattisgarh',
  'Rajasthan',
  'Sikkim',
  'Assam',
  'Manipur',
  'Chandigarh',
  'J&K',
  'Mizoram',
  'Daman & Diu',
  'Dadra & Nagar Haveli',
  'Lakshadweep',
  'Bihar',
  'Jharkhand',
  'Madhya Pradesh',
  'Tamil Nadu',
  'Andhra Pradesh',
  'Uttarakhand',
  'Himachal Pradesh',
  'Telangana',
  'Puducherry',
  'Andaman & Nicobar Islands',
  'Meghalaya',
  'Nagaland',
  'Gujarat',
  'Goa',
  'Kerala',
  'Delhi',
  'Maharashtra'
]


with open(awc_id_name_mapping_file) as _file:
    reader = csv.DictReader(_file)
    for row in reader:
        awc_id_name_mapping[row['awc_id']] = (row['awc_name'], row['state_name'])

# start with all
awc_ids_data_not_found = set(awc_id_name_mapping.keys())


output = []
with open(lat_long_file) as _file:
    reader = csv.DictReader(_file)
    for row in reader:
        if row['awc_id'] in awc_ids_data_not_found:
            awc_ids_data_not_found.remove(row['awc_id'])
        if row['awc_id'] not in awc_id_name_mapping:
            missing_awc_ids.append(row['awc_id'])
            location = SQLLocation.active_objects.get_or_None(location_id=row['awc_id'])
            if not location:
                print("Could not find location with %s" % row['awc_id'])
                continue
            state = location.get_ancestor_of_type('state')
            awc_id_name_mapping[row['awc_id']] = (location.name, state.name)
        state_name = awc_id_name_mapping[row['awc_id']][1]
        if state_name in real_location_names:
            o_row = copy(row)
            o_row['awc_name'] = awc_id_name_mapping[row['awc_id']][0]
            o_row['state_name'] = awc_id_name_mapping[row['awc_id']][1]
            output.append(o_row)
        elif state_name in test_location_names:
            skipped_test_location_data += 1
            print("test location data")
            print(row)
        else:
            unexpected_state_names.append(state_name)

print("Unexpected state names received: %s" % ','.join(unexpected_state_names))
print("Missing AWC IDs Count %s" % len(missing_awc_ids))
print("Test location data skipped %s" % skipped_test_location_data)
print("Data not found for %s awcs" % len(awc_ids_data_not_found))

# add no entry for locations there was no entry for
for awc_id in awc_ids_data_not_found:
    output.append({
        'awc_id': awc_id,
        'awc_name': awc_id_name_mapping[awc_id][0],
        'state_name': awc_id_name_mapping[awc_id][1],
        'form_location_lat': 'Data Not Entered',
        'form_location_long': 'Data Not Entered'
    })

# dump
with open('lat_long_reported_since_oct_2019.csv', 'w') as _file:
    writer = csv.DictWriter(_file, fieldnames=output[0].keys())
    writer.writeheader()
    for out in output:
        writer.writerow(out)
