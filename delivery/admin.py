from django.contrib import admin
from .models import DeliveryAgent, DeliveryAssignment, Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("number", "vehicle_type", "is_active", "created_at")
    list_filter = ("vehicle_type", "is_active")
    search_fields = ("number",)
    ordering = ("number",)


@admin.register(DeliveryAgent)
class DeliveryAgentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "username",
        "phone_number",
        "email",
        "is_available",
        "assigned_vehicle",
        "store_location",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "is_available", "store_location")
    search_fields = ("name", "phone_number", "email", "vehicle_number", "username")
    autocomplete_fields = ("assigned_vehicle", "store_location")
    ordering = ("name",)
    # Show only the requested fields on the form
    fields = (
        "name",
        "username",
        "phone_number",
        "email",
        "is_available",
        "assigned_vehicle",
        "store_location",
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        # If admin filtered by store_location, carry it over to the add form
        store_id = request.GET.get("store_location__id__exact") or request.GET.get("store_location")
        if store_id:
            initial["store_location"] = store_id
        return initial

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Require username input on the form
        if "username" in form.base_fields:
            form.base_fields["username"].required = True
            # Remove any help text under the username field
            form.base_fields["username"].help_text = ""
        return form

    # No custom FK filtering; show all choices


@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "agent",
        "status",
        "assigned_at",
        "expected_delivery_date",
        "delivered_at",
    )
    list_filter = ("status", "assigned_at", "delivered_at")
    search_fields = ("order__id", "agent__name")
    autocomplete_fields = ("agent", "order")
    date_hierarchy = "assigned_at"
    ordering = ("-assigned_at",)
