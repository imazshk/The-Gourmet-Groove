from django.contrib import admin
from .models import DeliveryEstimate, LogisticsPartner, ShipmentStatus, Shipment


@admin.register(DeliveryEstimate)
class DeliveryEstimateAdmin(admin.ModelAdmin):
    list_display = ("name", "min_days", "max_days")
    ordering = ("min_days", "max_days")
    search_fields = ("name",)


@admin.register(LogisticsPartner)
class LogisticsPartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_email", "phone_number", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_email", "phone_number")
    ordering = ("name",)


@admin.register(ShipmentStatus)
class ShipmentStatusAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "sequence")
    ordering = ("sequence",)
    search_fields = ("code", "label")


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "partner",
        "status",
        "tracking_no",
        "shipped_at",
        "estimated_delivery_date",
        "delivered_at",
    )
    list_filter = ("partner", "status")
    search_fields = ("order__id", "tracking_no", "partner__name")
    autocomplete_fields = ("order", "partner", "status", "delivery_estimate")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
