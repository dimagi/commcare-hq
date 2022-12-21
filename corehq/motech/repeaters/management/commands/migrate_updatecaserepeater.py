from corehq.motech.repeaters.management.commands.migrate_caserepeater import Command as MigrateCaseRepeaters
from corehq.motech.repeaters.models import SQLUpdateCaseRepeater


class Command(MigrateCaseRepeaters):

    @classmethod
    def couch_doc_type(cls):
        return 'UpdateCaseRepeater'

    @classmethod
    def sql_class(cls):
        return SQLUpdateCaseRepeater
