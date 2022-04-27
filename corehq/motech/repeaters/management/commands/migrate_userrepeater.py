from corehq.motech.repeaters.models import SQLUserRepeater
from corehq.motech.repeaters.utils import RepeaterMigrationHelper


class Command(RepeaterMigrationHelper):

    @classmethod
    def couch_doc_type(cls):
        return 'UserRepeater'

    @classmethod
    def sql_class(cls):
        return SQLUserRepeater
