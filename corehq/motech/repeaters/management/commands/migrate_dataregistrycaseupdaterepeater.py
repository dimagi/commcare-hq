from corehq.motech.repeaters.management.commands.migrate_caserepeater import Command as MigrateCaseRepeaters
from corehq.motech.repeaters.models import SQLDataRegistryCaseUpdateRepeater


class Command(MigrateCaseRepeaters):

    @classmethod
    def couch_doc_type(cls):
        return 'DataRegistryCaseUpdateRepeater'

    @classmethod
    def sql_class(cls):
        return SQLDataRegistryCaseUpdateRepeater
