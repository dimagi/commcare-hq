from django.db import models


class LedgerValue(models.Model):
    """
    Represents the current state of a ledger. Supercedes StockState
    """
    # domain not included and assumed to be accessed through the foreign key to the case table. legit?
    case_id = models.ForeignKey('CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=True)
    product_id = models.CharField(max_length=100, db_index=True)  # todo: make a foreign key to products?
    section_id = models.CharField(max_length=100, db_index=True)
    balance = models.IntegerField(default=0)  # todo: confirm we aren't ever intending to support decimals
    last_modified = models.DateTimeField(auto_now=True)  # I think this will be useful for restore.

    class Meta:
        # just until we actually use this for anything
        abstract = True
