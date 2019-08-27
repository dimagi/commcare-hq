
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zapier', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='zapiersubscription',
            name='case_type',
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='zapiersubscription',
            name='application_id',
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='zapiersubscription',
            name='form_xmlns',
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
    ]
