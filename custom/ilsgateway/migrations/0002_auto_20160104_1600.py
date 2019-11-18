from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ILSGatewayWebUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('external_id', models.IntegerField(db_index=True)),
                ('email', models.CharField(max_length=128)),
            ],
            options={
            },
            bases=(models.Model,),
        )
    ]
