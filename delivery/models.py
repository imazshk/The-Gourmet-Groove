from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

# Import Order from the existing store app
from store.models import Order
from stock_and_location.models import StoreLocation


class Vehicle(models.Model):
    VEHICLE_TYPES = [
        ("bike", "Bike"),
        ("scooter", "Scooter"),
        ("car", "Car"),
        ("van", "Van"),
        ("other", "Other"),
    ]

    number = models.CharField(max_length=30, unique=True, help_text="Registration/plate number")
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default="bike")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["number"]

    def __str__(self) -> str:
        return f"{self.number} ({self.get_vehicle_type_display()}){'' if self.is_active else ' - inactive'}"


class DeliveryAgent(models.Model):
    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        help_text="Username for this delivery agent (independent of site users)")
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True, help_text="Toggle availability for new assignments")
    assigned_vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="agents"
    )
    store_location = models.ForeignKey(
        StoreLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_agents"
    )
    vehicle_number = models.CharField(max_length=30, blank=True, null=True, help_text="Legacy-only; prefer Assigned vehicle")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        base = f"{self.name} / @{self.username}" if getattr(self, "username", None) else self.name
        suffix = []
        if not self.is_active:
            suffix.append("inactive")
        if not self.is_available:
            suffix.append("unavailable")
        return f"{base}{(' (' + ', '.join(suffix) + ')') if suffix else ''}"

    


class DeliveryAssignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        RETURNED = "returned", "Returned"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery_assignment")
    agent = models.ForeignKey(DeliveryAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name="assignments")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ASSIGNED)
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expected_delivery_date = models.DateField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Delivery Assignment"
        verbose_name_plural = "Delivery Assignments"

    def __str__(self):
        agent_name = self.agent.name if self.agent else "Unassigned"
        return f"Order #{self.order.id} → {agent_name} [{self.get_status_display()}]"

    def mark_delivered(self):
        self.status = self.Status.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at"]) 
