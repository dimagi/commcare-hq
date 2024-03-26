from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data_interfaces", "0037_add_dedupe_update_toggle"),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="caseduplicate",
            name="potential_duplicates",
            field=models.ManyToManyField(to="data_interfaces.caseduplicate"),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]
