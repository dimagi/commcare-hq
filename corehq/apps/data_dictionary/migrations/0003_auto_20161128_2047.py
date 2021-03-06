# Generated by Django 1.9.11 on 2016-11-28 20:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0002_auto_20161118_1537'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseproperty',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='caseproperty',
            name='type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('date', 'Date'),
                    ('plain', 'Plain'),
                    ('number', 'Number'),
                    ('select', 'Select'),
                    ('integer', 'Integer'),
                    ('', 'No Type Currently Selected')
                ],
                default='',
                max_length=20
            ),
        ),
        migrations.AlterField(
            model_name='casetype',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
    ]
