from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0003_auto_20200102_1006'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConnectionSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('name', models.CharField(max_length=255)),
                ('url', models.CharField(max_length=255)),
                ('auth_type', models.CharField(blank=True, choices=[
                    (None, 'None'), ('basic', 'Basic'), ('digest', 'Digest'), ('oauth1', 'OAuth1')
                ], max_length=7, null=True)),
                ('username', models.CharField(max_length=255)),
                ('password', models.CharField(max_length=255)),
                ('skip_cert_verify', models.BooleanField(default=False)),
                ('notify_addresses_str', models.CharField(default='', max_length=255)),
            ],
        ),
    ]
