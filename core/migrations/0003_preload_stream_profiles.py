# Generated by Django 5.1.6 on 2025-03-01 14:01

from django.db import migrations

def preload_stream_profiles(apps, schema_editor):
    StreamProfile = apps.get_model("core", "StreamProfile")
    StreamProfile.objects.create(
        profile_name="ffmpeg",
        command="ffmpeg",
        parameters="-i {streamUrl} -c:v copy -c:a copy -f mpegts pipe:1",
        is_active=True,
        user_agent="1",
    )

    StreamProfile.objects.create(
        profile_name="streamlink",
        command="streamlink",
        parameters="{streamUrl} best --stdout",
        is_active=True,
        user_agent="1",
    )

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_preload_user_agents'),
    ]

    operations = [
        migrations.RunPython(preload_stream_profiles),
    ]
