from corehq.motech.repeaters.models import SQLAppStructureRepeater
from corehq.motech.repeaters.utils import RepeaterMigrationHelper


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'AppStructureRepeater'

    @classmethod
    def sql_class(cls):
        return SQLAppStructureRepeater
