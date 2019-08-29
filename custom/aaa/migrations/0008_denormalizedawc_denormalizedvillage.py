# Generated by Django 1.11.20 on 2019-04-05 20:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aaa', '0007_auto_20190319_2225'),
    ]

    operations = [
        migrations.CreateModel(
            name='DenormalizedAWC',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.TextField()),
                ('state_id', models.TextField()),
                ('district_id', models.TextField()),
                ('block_id', models.TextField()),
                ('supervisor_id', models.TextField()),
                ('awc_id', models.TextField(unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='DenormalizedVillage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.TextField()),
                ('state_id', models.TextField()),
                ('district_id', models.TextField()),
                ('taluka_id', models.TextField()),
                ('phc_id', models.TextField()),
                ('sc_id', models.TextField()),
                ('village_id', models.TextField(unique=True)),
            ],
        ),
    ]
