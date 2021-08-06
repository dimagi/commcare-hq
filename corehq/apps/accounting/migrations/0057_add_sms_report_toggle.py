from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0056_add_release_management'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingaccount',
            name='is_sms_billable_report_visible',
            field=models.BooleanField(default=False),
        ),
    ]

