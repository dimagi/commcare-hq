from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0014_repeater_max_workers"),
    ]

    operations = [
        migrations.AlterField(
            model_name="repeater",
            name="is_paused",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AlterField(
            model_name="repeater",
            name="next_attempt_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name="repeatrecord",
            name="state",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Pending"),
                    (2, "Failed"),
                    (4, "Succeeded"),
                    (8, "Cancelled"),
                    (16, "Empty"),
                    (32, "Invalid Payload"),
                ],
                db_index=True,
                default=1,
            ),
        ),
    ]
