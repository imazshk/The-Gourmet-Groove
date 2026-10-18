from django.db import models
from django.utils import timezone

from store.models import Order


class DeliveryEstimate(models.Model):
    name = models.CharField(max_length=150)
    min_days = models.PositiveIntegerField(default=1)
    max_days = models.PositiveIntegerField(default=7)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["min_days", "max_days"]
        verbose_name = "Delivery Estimate"
        verbose_name_plural = "Delivery Estimates"

    def __str__(self) -> str:
        return f"{self.name} ({self.min_days}-{self.max_days} days)"


class LogisticsPartner(models.Model):
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    tracking_url_template = models.URLField(blank=True, null=True, help_text="Use {tracking_no} as placeholder")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Logistics Partner"
        verbose_name_plural = "Logistics Partners"

    def __str__(self) -> str:
        return f"{self.name}{' (inactive)' if not self.is_active else ''}"


class ShipmentStatus(models.Model):
    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=150)
    sequence = models.PositiveIntegerField(default=0, help_text="Ordering of statuses in progress")

    class Meta:
        ordering = ["sequence", "code"]
        verbose_name = "Shipment Status"
        verbose_name_plural = "Shipment Statuses"

    def __str__(self) -> str:
        return self.label


class Shipment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipment")
    partner = models.ForeignKey(LogisticsPartner, on_delete=models.SET_NULL, null=True, blank=True, related_name="shipments")
    status = models.ForeignKey(ShipmentStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name="shipments")
    tracking_no = models.CharField(max_length=100, blank=True, null=True)
    delivery_estimate = models.ForeignKey(DeliveryEstimate, on_delete=models.SET_NULL, null=True, blank=True, related_name="shipments")
    shipped_at = models.DateTimeField(blank=True, null=True)
    estimated_delivery_date = models.DateField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Shipment for Order #{self.order.id}"

    def mark_shipped(self):
        self.shipped_at = timezone.now()
        self.save(update_fields=["shipped_at"]) 

    def mark_delivered(self):
        self.delivered_at = timezone.now()
        self.save(update_fields=["delivered_at"]) 
