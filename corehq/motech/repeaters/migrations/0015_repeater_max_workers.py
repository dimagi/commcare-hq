from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0014_alter_repeater_is_paused_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="repeater",
            name="max_workers",
            field=models.IntegerField(default=0),
        ),
    ]
