from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0013_auto_20160826_1531')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
