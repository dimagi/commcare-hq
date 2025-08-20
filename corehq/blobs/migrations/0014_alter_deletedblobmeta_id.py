from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blobs", "0013_drop_icds_cas_index"),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="deletedblobmeta",
            name="id",
            field=models.IntegerField(primary_key=True, serialize=False),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations),
    ]
