from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('couchforms', '0004_unfinishedarchivestu'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='unfinishedsubmissionstu',
            index=models.Index(fields=['xform_id'], name='couchforms__xform_i_db4af3_idx'),
        ),
    ]
