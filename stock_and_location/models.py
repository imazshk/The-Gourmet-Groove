from django.db import models

from store.models import Chocolate


class StoreLocation(models.Model):
    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Store contact number")
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, default="India")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Store Location"
        verbose_name_plural = "Store Locations"

    def __str__(self) -> str:
        return self.name


class StorageLocation(models.Model):
    store = models.ForeignKey(StoreLocation, on_delete=models.CASCADE, related_name="storage_locations")
    name = models.CharField(max_length=150, help_text="Bin/Rack/Room identifier")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("store", "name")
        ordering = ["store__name", "name"]
        verbose_name = "Storage Location"
        verbose_name_plural = "Storage Locations"

    def __str__(self) -> str:
        return f"{self.store.name} - {self.name}"


class StorageQuantity(models.Model):
    item = models.ForeignKey(Chocolate, on_delete=models.CASCADE, related_name="storage_quantities")
    storage_location = models.ForeignKey(StorageLocation, on_delete=models.CASCADE, related_name="quantities")
    quantity = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("item", "storage_location")
        verbose_name = "Storage Quantity"
        verbose_name_plural = "Storage Quantities"

    def __str__(self) -> str:
        return f"{self.item.name} @ {self.storage_location}: {self.quantity}"
