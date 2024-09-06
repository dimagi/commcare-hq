from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0014_repeater_max_workers"),
    ]

    operations = [
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
        migrations.AddIndex(
            model_name="repeater",
            index=models.Index(
                condition=models.Q(("is_paused", False)),
                fields=["next_attempt_at"],
                name="next_attempt_at_not_paused_idx",
            ),
        ),
    ]
