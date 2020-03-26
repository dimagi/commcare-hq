from dimagi.utils.dates import force_to_datetime

from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class Command(PopulateSQLCommand):
    @classmethod
    def couch_db_slug(cls):
        return "users"

    @classmethod
    def couch_doc_type(self):
        return 'Invitation'

    @classmethod
    def sql_class(self):
        from corehq.apps.users.models import Invitation
        return Invitation

    @classmethod
    def commit_adding_migration(cls):
        return "3c6e3ea5b42834ac78b266b4e340af3d9a10481e"

    def update_or_create_sql_object(self, doc):
        model, created = self.sql_class().objects.update_or_create(
            couch_id=doc['_id'],
            defaults={
                "email": doc.get("email"),
                "invited_by": doc.get("invited_by"),
                "invited_on": force_to_datetime(doc.get("invited_on")),
                "is_accepted": doc.get("is_accepted", False),
                "domain": doc.get("domain"),
                "role": doc.get("role"),
                "program": doc.get("program"),
                "supply_point": doc.get("supply_point"),
            })
        return (model, created)
