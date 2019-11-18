from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ZapierSubscription',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('url', models.URLField(unique=True)),
                ('user_id', models.CharField(max_length=128)),
                ('domain', models.CharField(max_length=128)),
                ('event_name', models.CharField(max_length=128)),
                ('application_id', models.CharField(max_length=128)),
                ('form_xmlns', models.CharField(max_length=128)),
                ('repeater_id', models.CharField(max_length=128)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
