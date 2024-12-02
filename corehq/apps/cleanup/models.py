from django.db import models, transaction


class DeletedCouchDoc(models.Model):
    doc_id = models.CharField(max_length=126)
    doc_type = models.CharField(max_length=126)
    deleted_on = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['doc_id', 'doc_type'], name='deletedcouchdoc_unique_id_and_type')
        ]


class DeletedSQLDoc(models.Model):
    doc_id = models.CharField(max_length=126)
    object_class_path = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    deleted_on = models.DateTimeField(db_index=True)
    deleted_by = models.CharField(max_length=126, null=True)

    class Meta:
        db_table = "cleanup_deletedsqldoc"
        constraints = [
            models.UniqueConstraint(fields=['doc_id', 'object_class_path'],
                                    name='deletedsqldoc_unique_id_and_type')
        ]


def create_deleted_sql_doc(doc_id, class_path, domain, deleted_on, deleted_by=None):
    with transaction.atomic():
        return DeletedSQLDoc.objects.update_or_create(
            doc_id=doc_id, object_class_path=class_path,
            defaults={'deleted_on': deleted_on, 'deleted_by': deleted_by, 'domain': domain}
        )
