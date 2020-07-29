from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0019_deactivate_hardcoded_twilio_gateway_fees')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
