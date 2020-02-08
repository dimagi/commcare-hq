from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'DefaultConsumption'

    @classmethod
    def couch_key(self):
        return set(['couch_id'])

    @classmethod
    def sql_class(self):
        from corehq.apps.consumption.models import DefaultConsumption
        return DefaultConsumption

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.get_or_create(
            couch_id=doc['_id'],
            defaults={
                "type": doc.get("type"),
                "domain": doc.get("domain"),
                "product_id": doc.get("product_id"),
                "supply_point_type": doc.get("supply_point_type"),
                "supply_point_id": doc.get("supply_point_id"),
                "default_consumption": round(float(doc.get("default_consumption")), 8),
            })
        return (model, created)
