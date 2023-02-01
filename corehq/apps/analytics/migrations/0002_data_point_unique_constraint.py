# Generated by Django 2.2.27 on 2022-03-07 19:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0001_initial'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='partneranalyticsdatapoint',
            constraint=models.UniqueConstraint(fields=('slug', 'domain', 'year', 'month'), name='unique_per_month'),
        ),
    ]
