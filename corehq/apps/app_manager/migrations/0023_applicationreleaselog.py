# Generated by Django 3.2.16 on 2022-11-09 08:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0022_migrate_to_conditional_case_update'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApplicationReleaseLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(default='', max_length=255)),
                ('user_email', models.CharField(max_length=255)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('is_released', models.BooleanField()),
                ('version', models.CharField(max_length=255)),
                ('app_id', models.CharField(max_length=255)),
                ('user_id', models.CharField(max_length=255)),
            ],
        ),
    ]
