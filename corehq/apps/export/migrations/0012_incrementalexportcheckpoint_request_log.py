from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0008_requestlogpartitioned'),
        ('export', '0011_remove_incrementalexportcheckpoint_request_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='incrementalexportcheckpoint',
            name='request_log',
            field=models.ForeignKey(null=True,
                                    on_delete=django.db.models.deletion.CASCADE,
                                    to='motech.RequestLogPartitioned'),
        ),
    ]
