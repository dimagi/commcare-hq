from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0014_bootstrap_apposit_rates')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
