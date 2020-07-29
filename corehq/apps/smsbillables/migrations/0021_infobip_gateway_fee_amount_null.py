from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0020_update_sislog_fees')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
