from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ewsghana', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EWSExtension',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user_id', models.CharField(max_length=128, db_index=True)),
                ('domain', models.CharField(max_length=128)),
                ('location_id', models.CharField(max_length=128, null=True, db_index=True)),
                ('sms_notifications', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
