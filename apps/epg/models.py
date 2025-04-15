from django.db import models
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from .utils import enhance_mlb_description

class EPGSource(models.Model):
    SOURCE_TYPE_CHOICES = [
        ('xmltv', 'XMLTV URL'),
        ('schedules_direct', 'Schedules Direct API'),
    ]
    name = models.CharField(max_length=255, unique=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    url = models.URLField(blank=True, null=True)  # For XMLTV
    api_key = models.CharField(max_length=255, blank=True, null=True)  # For Schedules Direct
    is_active = models.BooleanField(default=True)
    file_path = models.CharField(max_length=1024, blank=True, null=True)
    refresh_interval = models.IntegerField(default=24)
    refresh_task = models.ForeignKey(
        PeriodicTask, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Time when this source was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Time when this source was last updated"
    )

    def __str__(self):
        return self.name

class EPGData(models.Model):
    # Removed the Channel foreign key. We now just store the original tvg_id
    # and a name (which might simply be the tvg_id if no real channel exists).
    tvg_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    epg_source = models.ForeignKey(
        EPGSource,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="epgs",
    )

    class Meta:
        unique_together = ('tvg_id', 'epg_source')

    def __str__(self):
        return f"EPG Data for {self.name}"

class ProgramData(models.Model):
    # Each programme is associated with an EPGData record.
    epg = models.ForeignKey(EPGData, on_delete=models.CASCADE, related_name="programs")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    title = models.CharField(max_length=255)
    sub_title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    tvg_id = models.CharField(max_length=255, null=True, blank=True)
    custom_properties = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.start_time} - {self.end_time})"

class Program(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100)
    start_time = models.DateTimeField()

    def save(self, *args, **kwargs):
        if "mlb" in self.category.lower():
            program_data = {
                "title": self.title,
                "desc": self.description,
                "category": self.category,
                "start": self.start_time.strftime("%Y%m%d%H%M%S")
            }
            enhanced = enhance_mlb_description(program_data)
            self.description = enhanced["desc"]
        super().save(*args, **kwargs)
