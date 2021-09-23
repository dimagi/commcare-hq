from django.db import models


class StockReport(models.Model):
    form_id = models.CharField(max_length=100, db_index=True)
    date = models.DateTimeField(db_index=True)
    type = models.CharField(max_length=20)  # currently "balance" or "transfer"
    domain = models.CharField(max_length=255, null=True)
    # should always equal the associated form's received_on property
    server_date = models.DateTimeField(null=True)

    # todo: there are properties like these that could be really useful for queries
    # and reports - should decide which ones we want to add if any.
    # they are all redundant via form_id linkage

    # server_date = models.DateTimeField(default=datetime.utcnow, db_index=True)
    # user_id = models.CharField(max_length=100, db_index=True)

    def __str__(self):
        return '{type} on {date} ({form})'.format(type=self.type, date=self.date, form=self.form_id)

    class Meta(object):
        app_label = 'stock'


class DocDomainMapping(models.Model):
    """
    Used to store the relationship between a doc and the
    domain it belongs to for efficient lookup
    """
    doc_id = models.CharField(max_length=100, db_index=True, primary_key=True)
    doc_type = models.CharField(max_length=100, db_index=True)
    domain_name = models.CharField(max_length=100, db_index=True)

    class Meta(object):
        app_label = 'stock'
