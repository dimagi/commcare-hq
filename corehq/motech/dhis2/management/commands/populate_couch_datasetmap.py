from django.core.management import BaseCommand

from ...models import DataSetMap, DataValueMap, SQLDataSetMap


class Command(BaseCommand):

    def handle(self, **options):
        i = None
        for i, sql_dataset_map in enumerate(
            SQLDataSetMap.objects.filter(couch_id__isnull=True)
        ):
            couch_dataset_map = DataSetMap(
                domain=sql_dataset_map.domain,
                connection_settings_id=sql_dataset_map.connection_settings.id,
                ucr_id=sql_dataset_map.ucr_id,
                description=sql_dataset_map.description,
                frequency=sql_dataset_map.frequency,
                day_to_send=sql_dataset_map.day_to_send,
                data_set_id=sql_dataset_map.data_set_id,
                org_unit_id=sql_dataset_map.org_unit_id,
                org_unit_column=sql_dataset_map.org_unit_column,
                period=sql_dataset_map.period,
                period_column=sql_dataset_map.period_column,
                attribute_option_combo_id=sql_dataset_map.attribute_option_combo_id,
                complete_date=sql_dataset_map.complete_date.isoformat(),
                datavalue_maps=[DataValueMap(
                    column=dvm.column,
                    data_element_id=dvm.data_element_id,
                    category_option_combo_id=dvm.category_option_combo_id,
                    comment=dvm.comment,
                ) for dvm in sql_dataset_map.datavalue_maps.all()]
            )
            couch_dataset_map.save()
            sql_dataset_map.couch_id = couch_dataset_map.get_id
            sql_dataset_map.save()

        if i is not None:
            print(f'Copied {i + 1} SQLDataSetMaps to CouchDB')
