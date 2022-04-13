# Generated by Django 2.2.27 on 2022-02-28 11:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth_integrations', '0002_livegooglesheetschedule'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiveGoogleSheetRefreshStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_start', models.DateTimeField(auto_now_add=True)),
                ('date_end', models.DateTimeField(blank=True, null=True)),
                ('refresh_error_reason', models.CharField(choices=[(None, 'No Error'), ('token', 'Invalid Token'), ('timeout', 'Data Timeout'), ('other', 'Other...')], default=None, max_length=7, null=True)),
                ('refresh_error_note', models.TextField(blank=True, null=True)),
                ('schedule', models.ForeignKey(on_delete=models.CASCADE, to='oauth_integrations.LiveGoogleSheetSchedule')),
            ],
        ),
    ]
