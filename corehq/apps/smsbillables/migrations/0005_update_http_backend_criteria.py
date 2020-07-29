from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0004_bootstrap_smsgh_rates')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
