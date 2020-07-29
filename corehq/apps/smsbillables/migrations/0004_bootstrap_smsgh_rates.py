from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0003_update_twilio_rates_outgoing')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
