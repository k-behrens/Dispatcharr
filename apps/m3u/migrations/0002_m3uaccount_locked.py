# Generated by Django 5.1.6 on 2025-03-17 20:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('m3u', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='m3uaccount',
            name='locked',
            field=models.BooleanField(default=False, help_text="Protected - can't be deleted or modified"),
        ),
    ]
