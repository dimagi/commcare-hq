from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='XFormAttachmentSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment_uuid', models.CharField(unique=True, max_length=255, db_index=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('content_type', models.CharField(max_length=255)),
                ('md5', models.CharField(max_length=255)),
                ('xform', models.ForeignKey(to='form_processor.XFormInstanceSQL', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
