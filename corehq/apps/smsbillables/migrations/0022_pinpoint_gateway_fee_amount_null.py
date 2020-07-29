from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0021_infobip_gateway_fee_amount_null')
    ]

    operations = [
        migrations.RunPython(noop)
    ]
