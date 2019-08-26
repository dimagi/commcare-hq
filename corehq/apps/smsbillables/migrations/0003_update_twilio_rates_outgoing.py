
from django.db import migrations




def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0002_bootstrap'),
    ]

    operations = {
        migrations.RunPython(noop),
    }
