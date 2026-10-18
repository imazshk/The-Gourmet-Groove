from django.contrib import admin
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from .models import Brand, Vendor, VendorStore, VendorProduct


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("name",)


class VendorStoreInline(admin.TabularInline):
    model = VendorStore
    fields = ("name", "address", "phone_number", "contact_email")
    extra = 1
    show_change_link = True


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "contact_email", "gst_no", "state", "is_active")
    list_filter = ("is_active", "state")
    search_fields = ("name", "contact_email", "phone_number", "gst_no", "state")
    ordering = ("name",)
    # No vendor-product bulk actions
    # No inlines; Vendor Stores managed from Vendor stores section only
    # Show only the requested fields on the add/edit form
    fields = (
        "name",
        "phone_number",
        "contact_email",
        "gst_no",
        "address",
        "state",
        "is_active",
    )

    




@admin.register(VendorStore)
class VendorStoreAdmin(admin.ModelAdmin):
    list_display = ("vendor", "name", "phone_number", "contact_email")
    list_filter = ()
    search_fields = ("name", "vendor__name", "phone_number", "contact_email")
    # Show vendor dropdown + requested fields on the form
    fields = (
        "vendor",
        "name",
        "address",
        "phone_number",
        "contact_email",
    )
    autocomplete_fields = ("vendor",)


@admin.register(VendorProduct)
class VendorProductAdmin(admin.ModelAdmin):
    list_display = ("vendor", "chocolate", "is_active")
    list_filter = ("is_active",)
    search_fields = ("vendor__name", "chocolate__name")
    autocomplete_fields = ("vendor", "chocolate")
    # Only show the requested fields on the add/edit form
    fields = (
        "vendor",
        "chocolate",
        "is_active",
    )
