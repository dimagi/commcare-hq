from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0012_formexpressionrepeater_arcgisformexpressionrepeater"),
    ]

    operations = [
        migrations.AddField(
            model_name="repeater",
            name="max_workers",
            field=models.IntegerField(default=7),
        ),
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
            name="domain",
            field=models.CharField(db_index=True, max_length=126),
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
                ],
                db_index=True,
                default=1,
            ),
        ),
    ]
