from django.contrib import admin

from .models import Product, Restaurant, Transaction, CartDetails, CustomerData, CustomerCreditsData, RestGallery, RestFeedback, RestSale, Chatbot
from .cv_models import CameraFeed, TableZone, OccupancySnapshot, OccupancyAnalytics

# Existing models
admin.site.register(Product)
admin.site.register(Restaurant)
admin.site.register(Transaction)
admin.site.register(CartDetails)
admin.site.register(CustomerData)
admin.site.register(CustomerCreditsData)
admin.site.register(RestGallery)
admin.site.register(RestFeedback)
admin.site.register(RestSale)
admin.site.register(Chatbot)


# CV Occupancy Models
@admin.register(CameraFeed)
class CameraFeedAdmin(admin.ModelAdmin):
    list_display = ('camera_id', 'name', 'restaurant', 'source_type', 'is_active', 'created_on')
    list_filter = ('source_type', 'is_active')


@admin.register(TableZone)
class TableZoneAdmin(admin.ModelAdmin):
    list_display = ('zone_id', 'label', 'restaurant', 'status', 'person_count', 'capacity', 'cooldown_seconds')
    list_filter = ('status', 'restaurant')


@admin.register(OccupancySnapshot)
class OccupancySnapshotAdmin(admin.ModelAdmin):
    list_display = ('snapshot_id', 'zone', 'status', 'person_count', 'confidence', 'timestamp')
    list_filter = ('status',)
    date_hierarchy = 'timestamp'


@admin.register(OccupancyAnalytics)
class OccupancyAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('analytics_id', 'restaurant', 'date', 'hour', 'avg_occupancy_pct', 'avg_turnover_minutes')
    list_filter = ('restaurant',)
    date_hierarchy = 'date'