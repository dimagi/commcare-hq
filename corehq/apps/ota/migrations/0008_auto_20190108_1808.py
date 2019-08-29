# Generated by Django 1.11.16 on 2019-01-08 18:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ota', '0007_update_blob_paths'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mobilerecoverymeasure',
            name='measure',
            field=models.CharField(choices=[('app_reinstall_and_update', 'Reinstall and Update App'), ('app_update', 'Update App'), ('cc_reinstall', 'CC Reinstall Needed'), ('cc_update', 'CC Update Needed'), ('app_offline_reinstall_and_update', 'Offline Reinstall and Update App')], help_text='<strong>Reinstall and Update App:</strong> Reinstall the current CommCare app either OTA or with a ccz, but requiring an OTA update to the latest version before it may be used.<br/><strong>Update App:</strong> Update the current CommCare app<br/><strong>CC Reinstall Needed:</strong> Notify the user that CommCare needs to be reinstalled<br/><strong>CC Update Needed:</strong> Notify the user that CommCare needs to be updated<br/><strong>Offline Reinstall and Update App:</strong> Reinstall the current CommCare app offline.', max_length=255),
        ),
    ]
