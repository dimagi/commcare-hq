# Generated by Django 2.2.25 on 2022-02-03 11:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0009_restrict_mob_access_from_FF'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectLimit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=256, unique=True)),
                ('limit_type', models.CharField(choices=[('lgs', 'Live Google Sheets')], max_length=5)),
            ],
        ),
    ]
