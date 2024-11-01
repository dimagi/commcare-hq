from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0012_formexpressionrepeater_arcgisformexpressionrepeater"),
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
                    (32, "Invalid Payload"),
                ]
            ),
        ),
    ]
