from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0047_rename_sqlpermission_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='hqapikey',
            name='expiration_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hqapikey',
            name='deactivated_on',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hqapikey',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
