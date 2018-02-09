from __future__ import absolute_import
from custom.enikshay.management.commands.base import ENikshayBatchCaseUpdaterCommand
from custom.enikshay.model_migration_sets.redeemed_prescription_vouchers import VoucherRedeemedDateSetter


class Command(ENikshayBatchCaseUpdaterCommand):
    updater = VoucherRedeemedDateSetter
