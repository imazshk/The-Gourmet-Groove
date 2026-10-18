from django.db import models
from django.contrib.auth.models import User

from store.models import Chocolate


class Brand(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Vendor(models.Model):
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    gst_no = models.CharField(max_length=30, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name}{' (inactive)' if not self.is_active else ''}"


class VendorStore(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="stores")
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, default="India")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vendor__name", "name"]

    def __str__(self) -> str:
        return f"{self.vendor.name} - {self.name}"


class VendorProduct(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_products")
    chocolate = models.ForeignKey(Chocolate, on_delete=models.CASCADE, related_name="vendor_products")
    sku = models.CharField(max_length=100, blank=True, null=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=0, help_text="Vendor's cost price")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("vendor", "chocolate")
        ordering = ["vendor__name", "chocolate__name"]
        verbose_name = "Vendor Product"
        verbose_name_plural = "Vendor Products"

    def __str__(self) -> str:
        return f"{self.vendor.name} - {self.chocolate.name}"
