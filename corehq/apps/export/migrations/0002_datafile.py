# Generated by Django 1.10.7 on 2017-06-21 14:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('export', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('filename', models.CharField(max_length=255)),
                ('description', models.CharField(max_length=255)),
                ('content_type', models.CharField(max_length=255)),
                ('blob_id', models.CharField(max_length=255)),
                ('content_length', models.IntegerField(null=True)),
            ],
        ),
    ]
