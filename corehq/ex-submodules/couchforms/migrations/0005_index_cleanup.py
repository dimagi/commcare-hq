from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('couchforms', '0004_unfinishedarchivestub'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='unfinishedsubmissionstub',
            index=models.Index(fields=['xform_id'], name='couchforms__xform_i_db4af3_idx'),
        ),
    ]
