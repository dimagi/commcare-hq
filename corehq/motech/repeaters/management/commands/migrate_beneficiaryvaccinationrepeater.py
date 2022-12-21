from corehq.motech.repeaters.management.commands.migrate_caserepeater import Command as MigrateCaseRepeaters
from custom.cowin.repeaters import SQLBeneficiaryVaccinationRepeater


class Command(MigrateCaseRepeaters):

    @classmethod
    def couch_doc_type(cls):
        return 'BeneficiaryVaccinationRepeater'

    @classmethod
    def sql_class(cls):
        return SQLBeneficiaryVaccinationRepeater
