# Generated by Django 2.2.24 on 2021-09-23 14:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0002_delete_stocktransaction'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],  # table to be deleted later
            state_operations=[
                migrations.DeleteModel(name='DocDomainMapping'),
                migrations.DeleteModel(name='StockReport'),
            ]
        ),
    ]
