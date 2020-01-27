from django.core.management import BaseCommand

from custom.icds_reports.utils.topojson_util.topojson_util import get_district_topojson_data


class Command(BaseCommand):
    help = "Prints out any districts whose names are duplicated across states."

    def handle(self, *args, **kwargs):
        district_topojson_data = get_district_topojson_data()
        districts_to_states = {}
        districts_with_duplicates = set()
        for state, data in district_topojson_data.items():
            for district_name in data['districts']:
                if district_name in districts_to_states:
                    districts_with_duplicates.add(district_name)
                    districts_to_states[district_name].append(state)
                else:
                    districts_to_states[district_name] = [state]
        print('District Name: [States]\n')
        for duplicate_district in districts_with_duplicates:
            print(f'{duplicate_district}: {", ".join(districts_to_states[duplicate_district])}')
