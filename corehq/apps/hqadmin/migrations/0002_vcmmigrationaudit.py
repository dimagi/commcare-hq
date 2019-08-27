
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='VCMMigrationAudit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=255)),
                ('emailed', models.DateTimeField(null=True)),
                ('migrated', models.DateTimeField()),
                ('notes', models.TextField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
