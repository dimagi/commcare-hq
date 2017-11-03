from custom.enikshay.management.commands.base import ENikshayBatchCaseUpdaterCommand
from custom.enikshay.model_migration_sets.private_nikshay_notifications import PrivateNikshayNotifiedDateSetter


class Command(ENikshayBatchCaseUpdaterCommand):
    updater = PrivateNikshayNotifiedDateSetter
