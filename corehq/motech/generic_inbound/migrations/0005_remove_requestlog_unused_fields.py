from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('generic_inbound', '0004_add_filter_expression'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='processingattempt',
            name='response_body',
        ),
        migrations.RemoveField(
            model_name='requestlog',
            name='error_message',
        ),
    ]
