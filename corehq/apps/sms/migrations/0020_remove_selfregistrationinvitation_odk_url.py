
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0019_add_new_registration_invitation_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='selfregistrationinvitation',
            name='odk_url',
        ),
    ]
