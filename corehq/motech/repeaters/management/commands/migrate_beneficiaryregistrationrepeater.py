from corehq.motech.repeaters.management.commands.migrate_caserepeater import Command as MigrateCaseRepeaters
from custom.cowin.repeaters import SQLBeneficiaryRegistrationRepeater


class Command(MigrateCaseRepeaters):

    @classmethod
    def couch_doc_type(cls):
        return 'BeneficiaryRegistrationRepeater'

    @classmethod
    def sql_class(cls):
        return SQLBeneficiaryRegistrationRepeater
