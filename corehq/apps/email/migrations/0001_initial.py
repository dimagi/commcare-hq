# Generated by Django 3.2.20 on 2023-09-19 15:45

from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='EmailSMTPBackend',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hq_api_id', models.CharField(max_length=126, null=True)),
                ('domain', models.CharField(db_index=True, max_length=126, null=True)),
                ('name', models.CharField(max_length=126, null=True)),
                ('display_name', models.CharField(max_length=126, null=True)),
                ('description', models.TextField(null=True)),
                ('username', models.CharField(max_length=100)),
                ('password', models.CharField(max_length=150)),
                ('server', models.CharField(max_length=50)),
                ('port', models.CharField(max_length=5)),
                ('extra_fields', jsonfield.fields.JSONField(default=dict)),
                ('is_default', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'messaging_emailbackend',
            },
        ),
        migrations.CreateModel(
            name='AWSBackend',
            fields=[
                ('emailsmtpbackend_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='email.emailsmtpbackend')),
            ],
            bases=('email.emailsmtpbackend',),
        ),
    ]
