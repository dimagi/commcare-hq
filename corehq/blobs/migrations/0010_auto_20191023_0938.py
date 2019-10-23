from django.db import migrations
import partial_index


class Migration(migrations.Migration):

    dependencies = [
        ('blobs', '0009_delete_blobexpiration'),
    ]

    operations = [
        migrations.RunSQL(migrations.RunSQL.noop, migrations.RunSQL.noop, state_operations=[
            migrations.RemoveIndex(
                model_name='blobmeta',
                name='blobs_blobm_expires_64b92d_partial',
            ),
            migrations.AddIndex(
                model_name='blobmeta',
                index=partial_index.PartialIndex(fields=['expires_on'], name='blobs_blobm_expires_ed7e3d_partial', unique=False, where=partial_index.PQ(expires_on__isnull=False)),
            )
        ]),
        migrations.AddIndex(
            model_name='blobmeta',
            index=partial_index.PartialIndex(fields=['type_code', 'created_on'], name='blobs_blobm_type_co_23e226_partial', unique=False, where=partial_index.PQ(domain='icds-cas')),
        ),
    ]
