from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0020_repeater_extra_backoff_codes"),
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
                    (32, "Payload Rejected"),
                    (64, "Error Generating Payload"),
                ],
                default=1,
            ),
        ),
        migrations.AlterField(
            model_name="repeatrecordattempt",
            name="state",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Pending"),
                    (2, "Failed"),
                    (4, "Succeeded"),
                    (8, "Cancelled"),
                    (16, "Empty"),
                    (32, "Payload Rejected"),
                    (64, "Error Generating Payload"),
                ]
            ),
        ),
    ]
