# Generated by Django 2.2.27 on 2022-03-08 20:09
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RunSQL("DROP TABLE IF EXISTS formplayer_entrysession", "SELECT 1"),
        migrations.RunSQL("DROP TABLE IF EXISTS formplayer_session", "SELECT 1"),
        migrations.RunSQL("DROP TABLE IF EXISTS formplayer_sqlstatus", "SELECT 1"),
        migrations.RunSQL("DROP TABLE IF EXISTS formplayer_xform", "SELECT 1"),
    ]
