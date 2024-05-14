from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("case_search", "0013_casesearchconfig_fuzzy_prefix_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="casesearchconfig",
            name="index_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Name or alias of alternative index to use for case search",
                max_length=256,
            ),
        ),
    ]
