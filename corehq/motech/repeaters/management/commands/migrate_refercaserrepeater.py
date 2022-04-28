from corehq.motech.repeaters.models import SQLReferCaseRepeater
from corehq.motech.repeaters.management.commands.migrate_caserepeater import Command as MigrateCaseRepeaters


class Command(MigrateCaseRepeaters):

    @classmethod
    def couch_doc_type(cls):
        return 'ReferCaseRepeater'

    @classmethod
    def sql_class(cls):
        return SQLReferCaseRepeater
