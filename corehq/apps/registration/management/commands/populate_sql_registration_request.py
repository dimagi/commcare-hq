from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'RegistrationRequest'

    @classmethod
    def couch_key(self):
        return set(['activation_guid'])

    @classmethod
    def sql_class(self):
        from corehq.apps.registration.models import RegistrationRequest
        return RegistrationRequest

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.get_or_create(
            activation_guid=doc['activation_guid'],
            defaults={
                "tos_confirmed": doc.get("tos_confirmed"),
                "request_time": doc.get("request_time"),
                "request_ip": doc.get("request_ip"),
                "confirm_time": doc.get("confirm_time"),
                "confirm_ip": doc.get("confirm_ip"),
                "domain": doc.get("domain"),
                "new_user_username": doc.get("new_user_username"),
                "requesting_user_username": doc.get("requesting_user_username"),
            })
        return (model, created)
