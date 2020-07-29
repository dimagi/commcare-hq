from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0018_index__date_sent')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
