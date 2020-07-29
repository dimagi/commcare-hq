from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0001_initial')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
