import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_data_fields', '0008_custom_data_fields_upstream_ids'),
        ('users', '0054_connectiduserlink'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLUserData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=128)),
                ('user_id', models.CharField(max_length=36)),
                ('modified_on', models.DateTimeField(auto_now=True)),
                ('data', models.JSONField()),
                ('profile', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='custom_data_fields.customdatafieldsprofile')),
            ],
        ),
        migrations.AddIndex(
            model_name='sqluserdata',
            index=models.Index(fields=['user_id', 'domain'], name='users_sqlus_user_id_f129be_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='sqluserdata',
            unique_together={('user_id', 'domain')},
        ),
    ]
