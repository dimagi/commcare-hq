# Generated by Django 1.11.13 on 2018-07-09 18:33

from datetime import date

from django.db import migrations


def assert_date_delay_invoicing_does_not_apply(apps, schema_editor):
    Subscription = apps.get_model('accounting', 'Subscription')
    assert not Subscription.visible_objects.filter(
        date_delay_invoicing__isnull=False,
        date_delay_invoicing__gt=date(2018, 1, 1),
    ).exists()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0033_auto_20180709_1837'),
    ]

    operations = [
        migrations.RunPython(assert_date_delay_invoicing_does_not_apply, reverse_code=migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='subscription',
            name='date_delay_invoicing',
        ),
    ]
