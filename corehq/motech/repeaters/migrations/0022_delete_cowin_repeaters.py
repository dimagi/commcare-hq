from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("repeaters", "0021_alter_repeatrecord_state_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name='BeneficiaryRegistrationRepeater',
        ),
        migrations.DeleteModel(
            name='BeneficiaryVaccinationRepeater',
        ),
        migrations.DeleteModel(
            name='BaseCOWINRepeater',
        ),
    ]
