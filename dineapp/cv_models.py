"""
CV Models — Database models for the Computer Vision table occupancy system.
Stores camera configurations, table zone polygons, occupancy snapshots, and analytics.
"""

from django.db import models
from .models import Restaurant


class CameraFeed(models.Model):
    """Represents a camera source (RTSP stream, webcam, or uploaded video file)."""
    objects: models.Manager['CameraFeed']
    camera_id = models.AutoField(primary_key=True)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='cameras')
    name = models.CharField(max_length=100, default="Main Camera")
    source_type = models.CharField(
        max_length=20,
        choices=[
            ('video_file', 'Video File'),
            ('webcam', 'Webcam'),
            ('rtsp', 'RTSP Stream'),
        ],
        default='video_file'
    )
    source_path = models.TextField(default="")  # File path, webcam index, or RTSP URL
    static_frame = models.TextField(default="*")  # Base64 of calibration frame
    is_active = models.BooleanField(default=False)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Camera {self.camera_id}: {self.name} ({self.source_type}) — {self.restaurant.name}"


class TableZone(models.Model):
    """
    Defines a polygon Region of Interest (ROI) for a table in the camera frame.
    Coordinates are stored as JSON: [[x1,y1], [x2,y2], [x3,y3], ...]
    """
    objects: models.Manager['TableZone']
    DoesNotExist: type[Exception]
    zone_id = models.AutoField(primary_key=True)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='table_zones')
    camera = models.ForeignKey(CameraFeed, on_delete=models.CASCADE, related_name='zones')
    label = models.CharField(max_length=50, default="Table 1")
    polygon_coords = models.JSONField(default=list)  # [[x1,y1], [x2,y2], ...]
    capacity = models.IntegerField(default=4)
    cooldown_seconds = models.IntegerField(default=300)  # 5 minutes default
    status = models.CharField(
        max_length=20,
        choices=[
            ('available', 'Available'),
            ('occupied', 'Occupied'),
            ('cooldown', 'Cooldown'),
        ],
        default='available'
    )
    person_count = models.IntegerField(default=0)
    last_status_change = models.DateTimeField(auto_now=True)
    color = models.CharField(max_length=7, default="#00e676")  # Hex color for display

    def __str__(self):
        return f"Zone {self.zone_id}: {self.label} — {self.status} — {self.restaurant.name}"


class OccupancySnapshot(models.Model):
    """Time-series record of a zone's occupancy state. Written every ~30 seconds by the CV pipeline."""
    objects: models.Manager['OccupancySnapshot']
    snapshot_id = models.AutoField(primary_key=True)
    zone = models.ForeignKey(TableZone, on_delete=models.CASCADE, related_name='snapshots')
    status = models.CharField(max_length=20)  # occupied / available / cooldown
    person_count = models.IntegerField(default=0)
    confidence = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['zone', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]

    def __str__(self):
        return f"Snapshot: {self.zone.label} — {self.status} ({self.person_count} people) @ {self.timestamp}"


class OccupancyAnalytics(models.Model):
    """Aggregated hourly analytics — computed by the analytics engine from snapshots."""
    objects: models.Manager['OccupancyAnalytics']
    analytics_id = models.AutoField(primary_key=True)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='occupancy_analytics')
    date = models.DateField()
    hour = models.IntegerField()  # 0-23
    avg_occupancy_pct = models.FloatField(default=0.0)  # 0-100
    total_tables = models.IntegerField(default=0)
    avg_occupied_tables = models.FloatField(default=0.0)
    avg_turnover_minutes = models.FloatField(default=0.0)
    peak_person_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ['restaurant', 'date', 'hour']
        ordering = ['date', 'hour']

    def __str__(self):
        return f"Analytics: {self.restaurant.name} — {self.date} H{self.hour} — {self.avg_occupancy_pct:.1f}%"
