from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ota', '0003_add_serial_id_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='MobileRecoveryMeasure',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('measure', models.CharField(choices=[('app_reinstall_ota', 'Reinstall App, OTA'), ('app_reinstall_local', 'Reinstall App, Local'), ('app_update', 'Update App'), ('clear_data', 'Clear User Data'), ('cc_reinstall', 'CC Reinstall Needed'), ('cc_update', 'CC Update Needed')], help_text="<strong>Reinstall App, OTA:</strong> Reinstall the current CommCare app by triggering an OTA install<br/><strong>Reinstall App, Local:</strong> Reinstall the current CommCare app (by triggering an offline install with a default .ccz that's already on the device, and then doing an OTA update from there)<br/><strong>Update App:</strong> Update the current CommCare app<br/><strong>Clear User Data:</strong> Clear data for the app's last logged in user<br/><strong>CC Reinstall Needed:</strong> Notify the user that CommCare needs to be reinstalled<br/><strong>CC Update Needed:</strong> Notify the user that CommCare needs to be updated", max_length=255)),
                ('domain', models.CharField(max_length=255)),
                ('app_id', models.CharField(max_length=50)),
                ('cc_all_versions', models.BooleanField(default=True, verbose_name='All CommCare Versions')),
                ('cc_version_min', models.CharField(blank=True, max_length=255, verbose_name='Min CommCare Version')),
                ('cc_version_max', models.CharField(blank=True, max_length=255, verbose_name='Max CommCare Version')),
                ('app_all_versions', models.BooleanField(default=True, verbose_name='All App Versions')),
                ('app_version_min', models.IntegerField(blank=True, max_length=255, null=True, verbose_name='Min App Version')),
                ('app_version_max', models.IntegerField(blank=True, max_length=255, null=True, verbose_name='Max App Version')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('username', models.CharField(editable=False, max_length=255)),
                ('notes', models.TextField(blank=True)),
            ],
        ),
    ]
