from dimagi.utils.dates import force_to_datetime

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'RegistrationRequest'

    @classmethod
    def sql_class(self):
        from corehq.apps.registration.models import RegistrationRequest
        return RegistrationRequest

    @classmethod
    def commit_adding_migration(cls):
        return "61dc4670073baf7c51b7ab23cccbf16e3ecedbe9"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "activation_guid": doc.get('activation_guid'),
                "tos_confirmed": doc.get("tos_confirmed"),
                "request_time": force_to_datetime(doc.get("request_time")),
                "request_ip": doc.get("request_ip"),
                "confirm_time": force_to_datetime(doc.get("confirm_time")),
                "confirm_ip": doc.get("confirm_ip"),
                "domain": doc.get("domain"),
                "new_user_username": doc.get("new_user_username"),
                "requesting_user_username": doc.get("requesting_user_username"),
            })
        return (model, created)
