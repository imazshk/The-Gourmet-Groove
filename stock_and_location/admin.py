from django.contrib import admin
from .models import StoreLocation, StorageLocation, StorageQuantity


@admin.register(StoreLocation)
class StoreLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "city", "state", "country", "is_active")
    list_filter = ("is_active", "country", "state")
    search_fields = ("name", "phone_number", "city", "state")
    ordering = ("name",)


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ("store", "name", "is_active")
    list_filter = ("is_active", "store")
    search_fields = ("name", "store__name")
    autocomplete_fields = ("store",)


@admin.register(StorageQuantity)
class StorageQuantityAdmin(admin.ModelAdmin):
    list_display = ("item", "storage_location", "quantity", "last_updated")
    list_filter = ("storage_location__store",)
    search_fields = ("item__name", "storage_location__name")
    autocomplete_fields = ("item", "storage_location")
    ordering = ("-last_updated",)
