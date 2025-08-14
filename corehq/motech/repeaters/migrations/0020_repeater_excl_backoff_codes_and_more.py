import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0019_connectformrepeater"),
    ]

    operations = [
        migrations.AddField(
            model_name="repeater",
            name="excl_backoff_codes",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                default=list,
                help_text="Do not back off / retry these HTTP response codes",
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="repeater",
            name="incl_backoff_codes",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.IntegerField(),
                default=list,
                help_text="Also back off / retry these HTTP response codes",
                size=None,
            ),
        ),
    ]
