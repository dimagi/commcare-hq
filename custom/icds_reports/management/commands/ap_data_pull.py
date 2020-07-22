import csv
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Sum

from custom.icds_reports.models import AggCcsRecord, AggChildHealth, AwcLocation

STATE_ID = 'f98e91aa003accb7b849a0f18ebd7039'


class Command(BaseCommand):

    def handle(self, **options):
        headers = [
            'district_name',
            'sc_pregnant', 'st_pregnant', 'obc_pregnant', 'other_pregnant', 'minority_pregnant',
            'sc_lactating', 'st_lactating', 'obc_lactating', 'other_lactating', 'minority_lactating',
            'sc_ch_6_to_3yr', 'st_ch_6_to_3yr', 'obc_ch_6_to_3yr', 'other_ch_6_to_3yr', 'minority_ch_6_to_3yr',
            'sc_ch_3_to_6yr', 'st_ch_3_to_6yr', 'obc_ch_3_to_6yr', 'other_ch_3_to_6yr', 'minority_ch_3_to_6yr']
        dummy_row = [0 for _ in range(0, len(headers) - 1)]
        excel_rows = [headers]
        locations = AwcLocation.objects.filter(state_id=STATE_ID, aggregation_level=2).values('district_id',
                                                                                              'district_name')
        data = {}
        for loc in locations:
            data[loc['district_id']] = [loc['district_name']] + dummy_row

        # pregnant and lactating st, sc, obc, others
        rows = AggCcsRecord.objects.filter(
                month=date(2020, 6, 1), aggregation_level=5).values('district_id', 'caste').order_by().annotate(
                pregnant=Sum('pregnant'), lactating=Sum('lactating'))
        for row in rows:
            district_id = row['district_id']
            caste = row['caste']
            if caste is not None:
                data[district_id][headers.index(f'{caste}_pregnant')] = row['pregnant']
                data[district_id][headers.index(f'{caste}_lactating')] = row['lactating']
        # pregnant and lactating minority
        rows = AggCcsRecord.objects.filter(
                month=date(2020, 6, 1), state_id=STATE_ID, minority='yes', aggregation_level=5).values(
                'district_id', ).order_by().annotate(pregnant=Sum('pregnant'), lactating=Sum('lactating'))
        for row in rows:
            district_id = row['district_id']
            data[district_id][headers.index('minority_pregnant')] = row['pregnant']
            data[district_id][headers.index('minority_lactating')] = row['lactating']

        # child 6 months - 3 years sc, st, obc, others
        rows = AggChildHealth.objects.filter(
                month=date(2020, 6, 1), state_id=STATE_ID, aggregation_level=5,
                age_tranche__in=['12', '24', '36']).values('district_id', 'caste').order_by().annotate(
                valid_count=Sum('valid_in_month'))
        for row in rows:
            district_id = row['district_id']
            caste = row['caste']
            if caste is not None:
                data[district_id][headers.index(f'{caste}_ch_6_to_3yr')] = row['valid_count']

        # child 3 years - 6 years sc, st, obc, others
        rows = AggChildHealth.objects.filter(
                month=date(2020, 6, 1), state_id=STATE_ID, aggregation_level=5,
                age_tranche__in=['48', '60', '72']).values('district_id', 'caste').order_by().annotate(
            valid_count=Sum('valid_in_month'))
        for row in rows:
            district_id = row['district_id']
            caste = row['caste']
            if caste is not None:
                data[district_id][headers.index(f'{caste}_ch_3_to_6yr')] = row['valid_count']

        # child 6 months - 3 years minority
        rows = AggChildHealth.objects.filter(
                month=date(2020, 6, 1), state_id=STATE_ID, minority='yes', aggregation_level=5,
                age_tranche__in=['12', '24', '36']).values('district_id').order_by().annotate(
            valid_count=Sum('valid_in_month'))
        for row in rows:
            district_id = row['district_id']
            data[district_id][headers.index('minority_ch_6_to_3yr')] = row['valid_count']

        # child 3 years - 6 years minority
        rows = AggChildHealth.objects.filter(
                month=date(2020, 6, 1), state_id=STATE_ID, minority='yes', aggregation_level=5,
                age_tranche__in=['48', '60', '72']).values('district_id').order_by().annotate(
            valid_count=Sum('valid_in_month'))
        for row in rows:
            district_id = row['district_id']
            data[district_id][headers.index('minority_ch_3_to_6yr')] = row['valid_count']

        for _, val in data.items():
            excel_rows.append(val)
        fout = open('/home/cchq/ap_benefic_data.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(excel_rows)
