from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0015_drop_receiverwrapper_couchdb"),
    ]

    operations = [
        migrations.AddField(
            model_name="repeater",
            name="max_workers",
            field=models.IntegerField(default=0),
        ),
    ]
