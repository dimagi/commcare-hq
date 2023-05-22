from django.db import models


class DeletedCouchDoc(models.Model):
    doc_id = models.CharField(max_length=126)  # doc ids are unique across couch
    deleted_on = models.DateTimeField(db_index=True)
