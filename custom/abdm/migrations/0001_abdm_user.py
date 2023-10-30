# Generated by Django 3.2.20 on 2023-10-30 14:40

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ABDMUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=100)),
                ('access_token', models.CharField(blank=True, max_length=2000, null=True)),
                ('domain', models.CharField(max_length=100)),
            ],
            options={
                'unique_together': {('username', 'domain')},
            },
        ),
    ]
