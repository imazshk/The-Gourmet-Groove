from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import redirect, get_object_or_404
from django.utils.html import format_html
from .models import Chocolate, Order, Category, Coupon, CouponUsage, Brand, Notification, ReturnRequest

@admin.register(Chocolate)
class ChocolateAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'category', 'brand', 'rating', 'total_sales']
    list_filter = ['category', 'brand', 'created_at']
    search_fields = ['name', 'description']

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_top']
    fields = ['name', 'image', 'is_top']
    list_filter = ['is_top']
    search_fields = ['name']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['user', 'chocolate', 'quantity', 'total_price', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'chocolate__name', 'invoice_number']
    readonly_fields = ['invoice_number', 'created_at']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'minimum_order_amount', 'usage_limit', 'used_count', 'is_active', 'valid_from', 'valid_until']
    list_filter = ['discount_type', 'is_active', 'valid_from', 'valid_until']
    search_fields = ['code', 'description']
    readonly_fields = ['used_count', 'created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new coupons
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.is_staff
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'short_message',
        'is_read',
        'created_at',
        'return_request',
    ]
    list_filter = ['is_read', 'created_at']
    search_fields = ['user__username', 'message']
    readonly_fields = ['user', 'message', 'created_at', 'return_request']
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['mark_as_read', 'mark_as_unread']

    def short_message(self, obj):
        return (obj.message or '')[:60] + ('…' if obj.message and len(obj.message) > 60 else '')
    short_message.short_description = 'Message'

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"Marked {updated} notification(s) as read.")
    mark_as_read.short_description = 'Mark selected notifications as read'

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"Marked {updated} notification(s) as unread.")
    mark_as_unread.short_description = 'Mark selected notifications as unread'


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'user', 'reason', 'status', 'created_at', 'updated_at', 'decided_by', 'approve_btn', 'decline_btn']
    list_filter = ['status', 'reason', 'created_at']
    search_fields = ['order__invoice_number', 'user__username']
    readonly_fields = ['user', 'order', 'created_at', 'updated_at']
    ordering = ('-created_at',)
    actions = ['approve_requests', 'decline_requests']

    # --- Inline buttons in changelist ---
    def approve_btn(self, obj):
        if obj.status == ReturnRequest.Status.PENDING:
            url = reverse('admin:store_returnrequest_approve', args=[obj.pk])
            return format_html('<a class="button" href="{}">Approve</a>', url)
        return '-'
    approve_btn.short_description = ''
    approve_btn.allow_tags = True

    def decline_btn(self, obj):
        if obj.status == ReturnRequest.Status.PENDING:
            url = reverse('admin:store_returnrequest_decline', args=[obj.pk])
            return format_html('<a class="button" style="background:#a00;color:#fff;" href="{}">Decline</a>', url)
        return '-'
    decline_btn.short_description = ''
    decline_btn.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/approve/', self.admin_site.admin_view(self.approve_view), name='store_returnrequest_approve'),
            path('<int:pk>/decline/', self.admin_site.admin_view(self.decline_view), name='store_returnrequest_decline'),
        ]
        return custom_urls + urls

    def _change_status(self, request, pk, new_status, success_msg):
        rr = get_object_or_404(ReturnRequest, pk=pk)
        if rr.status != new_status:
            rr.status = new_status
            rr.decided_by = request.user
            rr.save()
            Notification.objects.create(
                user=rr.user,
                message=f"Your return request for order {rr.order.invoice_number} is {new_status}.",
                return_request=rr,
            )
            messages.success(request, success_msg)
        else:
            messages.info(request, f"Already {new_status}.")
        # Redirect back to changelist
        changelist_url = reverse('admin:store_returnrequest_changelist')
        return redirect(request.META.get('HTTP_REFERER', changelist_url))

    def approve_view(self, request, pk, *args, **kwargs):
        return self._change_status(request, pk, ReturnRequest.Status.APPROVED, 'Return request approved.')

    def decline_view(self, request, pk, *args, **kwargs):
        return self._change_status(request, pk, ReturnRequest.Status.DECLINED, 'Return request declined.')

    def save_model(self, request, obj, form, change):
        # When admin changes status manually, set decided_by if transitioning out of pending
        if change and 'status' in form.changed_data and obj.status in [ReturnRequest.Status.APPROVED, ReturnRequest.Status.DECLINED]:
            obj.decided_by = request.user
        super().save_model(request, obj, form, change)
        # Create a notification reflecting the latest status
        Notification.objects.create(
            user=obj.user,
            message=f"Your return request for order {obj.order.invoice_number} is {obj.status}.",
            return_request=obj,
        )

    def approve_requests(self, request, queryset):
        updated = 0
        for rr in queryset:
            if rr.status != ReturnRequest.Status.APPROVED:
                rr.status = ReturnRequest.Status.APPROVED
                rr.decided_by = request.user
                rr.save()
                Notification.objects.create(
                    user=rr.user,
                    message=f"Your return request for order {rr.order.invoice_number} is approved.",
                    return_request=rr,
                )
                updated += 1
        self.message_user(request, f"Approved {updated} return request(s).")
    approve_requests.short_description = 'Approve selected return requests'

    def decline_requests(self, request, queryset):
        updated = 0
        for rr in queryset:
            if rr.status != ReturnRequest.Status.DECLINED:
                rr.status = ReturnRequest.Status.DECLINED
                rr.decided_by = request.user
                rr.save()
                Notification.objects.create(
                    user=rr.user,
                    message=f"Your return request for order {rr.order.invoice_number} is declined.",
                    return_request=rr,
                )
                updated += 1
        self.message_user(request, f"Declined {updated} return request(s).")
    decline_requests.short_description = 'Decline selected return requests'

@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['coupon', 'user', 'order', 'discount_amount', 'used_at']
    list_filter = ['used_at', 'coupon']
    search_fields = ['coupon__code', 'user__username']
    readonly_fields = ['coupon', 'user', 'order', 'discount_amount', 'used_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
