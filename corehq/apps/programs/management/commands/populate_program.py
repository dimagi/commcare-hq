from corehq.apps.cleanup.management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand
from corehq.apps.groups.models import dt_no_Z_re


class Command(PopulateSQLCommand):
    @classmethod
    def couch_doc_type(self):
        return 'Program'

    @classmethod
    def couch_key(self):
        return set(['couch_id'])

    @classmethod
    def sql_class(self):
        from corehq.apps.programs.models import SQLProgram
        return SQLProgram

    def update_or_create_sql_object(self, doc):
        # If "Z" is missing because of the Aug 2014 migration, then add it.
        # cf. Group class
        last_modified = doc.get('last_modified')
        if last_modified and dt_no_Z_re.match(last_modified):
            doc['last_modified'] += 'Z'

        # TODO: find and update or create SQL object. Use SyncSQLToCouchMixin and SyncCouchToSQLMixin.

        return (model, created)
