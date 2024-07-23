from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data_interfaces", "0037_add_dedupe_update_toggle"),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="caseduplicate",
            name="potential_duplicates",
            # Django < 4 specified related_name in ManyToManyField, whereas Django >= 4 does not.
            # This results in a new migration being created on 4 that is virtually a no-op.
            field=models.ManyToManyField(to="data_interfaces.caseduplicate"),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]
