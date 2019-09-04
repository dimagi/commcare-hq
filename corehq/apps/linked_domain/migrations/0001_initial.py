# Generated by Django 1.11.9 on 2018-02-01 15:00

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DomainLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('linked_domain', models.CharField(max_length=126, unique=True)),
                ('master_domain', models.CharField(max_length=126)),
                ('last_pull', models.DateTimeField(auto_now_add=True)),
                ('remote_base_url', models.CharField(max_length=255, null=True)),
                ('remote_username', models.CharField(max_length=255, null=True)),
                ('remote_api_key', models.CharField(max_length=255, null=True)),
            ],
        ),
    ]
