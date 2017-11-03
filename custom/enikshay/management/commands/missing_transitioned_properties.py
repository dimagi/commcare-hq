from custom.enikshay.management.commands.base import ENikshayBatchCaseUpdaterCommand
from custom.enikshay.model_migration_sets.transitioned_patients_missing_properties import (
    TransitionedPatientsMissingProperties,
)


class Command(ENikshayBatchCaseUpdaterCommand):
    updater = TransitionedPatientsMissingProperties
