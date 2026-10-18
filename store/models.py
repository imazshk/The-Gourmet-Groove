from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    image = models.ImageField(upload_to='brands/', blank=True, null=True)
    is_top = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Chocolate(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='chocolates/')
    price = models.DecimalField(max_digits=8, decimal_places=2)
    file = models.FileField(upload_to='downloads/', blank=True, null=True)
    tags = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    rating = models.FloatField(default=0)
    total_ratings = models.PositiveIntegerField(default=0)
    total_sales = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def update_rating(self):
        """Update average rating based on reviews"""
        reviews = self.review_set.all()
        if reviews:
            self.rating = sum(review.rating for review in reviews) / len(reviews)
            self.total_ratings = len(reviews)
        else:
            self.rating = 0
            self.total_ratings = 0
        self.save()

    def is_trending(self):
        """Check if product is trending (most selling)"""
        return self.total_sales > 0

    def is_new(self):
        """Check if product was added today"""
        return self.created_at.date() == timezone.now().date()

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def is_birthday_today(self):
        """Check if today is user's birthday"""
        if self.birth_date:
            today = timezone.now().date()
            return self.birth_date.month == today.month and self.birth_date.day == today.day
        return False

class UserAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='India')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.address_line1}, {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other addresses of this user to non-default
            UserAddress.objects.filter(user=self.user).update(is_default=False)
        super().save(*args, **kwargs)

class Order(models.Model):
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chocolate = models.ForeignKey(Chocolate, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    address = models.ForeignKey(UserAddress, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivery_status = models.CharField(
        max_length=20, 
        choices=DELIVERY_STATUS_CHOICES, 
        default='pending'
    )
    invoice_number = models.CharField(max_length=50, unique=True, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.chocolate.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Update product sales count
        if self.pk is None:  # New order
            self.chocolate.total_sales += self.quantity
            self.chocolate.save()
        
        super().save(*args, **kwargs)

    def subtotal(self):
        return self.chocolate.price * self.quantity

    def total_price(self):
        # This avoids the error if discount is not attached via CouponUsage
        try:
            coupon_usage = CouponUsage.objects.get(order=self)
            return max(self.subtotal() - coupon_usage.discount_amount, 0)
        except CouponUsage.DoesNotExist:
            return self.subtotal()


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chocolate = models.ForeignKey(Chocolate, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.chocolate.name} x {self.quantity}"

    def total_price(self):
        return self.chocolate.price * self.quantity

class WishlistItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chocolate = models.ForeignKey(Chocolate, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'chocolate']

    def __str__(self):
        return f"{self.user.username} - {self.chocolate.name}"

class CartShare(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    share_token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.share_token}"

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = uuid.uuid4().hex
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chocolate = models.ForeignKey(Chocolate, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'chocolate', 'order']

    def __str__(self):
        return f"{self.user.username} - {self.chocolate.name} - {self.rating} stars"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update chocolate rating
        self.chocolate.update_rating()

class BirthdayOffer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    discount_percentage = models.PositiveIntegerField(default=10)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Birthday offer for {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Set expiry to 30 days from creation
            self.expires_at = timezone.now() + timezone.timedelta(days=30)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maximum_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited usage")
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_coupons')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.get_discount_display()}"

    def get_discount_display(self):
        if self.discount_type == 'percentage':
            return f"{self.discount_value}% off"
        else:
            return f"₹{self.discount_value} off"

    def is_valid(self):
        """Check if coupon is valid for use"""
        now = timezone.now()
        return (
            self.is_active and
            self.valid_from <= now <= self.valid_until and
            (self.usage_limit is None or self.used_count < self.usage_limit)
        )

    def can_be_used_by_user(self, user, order_amount):
        """Check if coupon can be used by a specific user for a specific order amount"""
        if not self.is_valid():
            return False, "Coupon is not valid"

        # Enforce minimum order amount (generic)
        if order_amount < self.minimum_order_amount:
            return False, f"Minimum order amount is ₹{self.minimum_order_amount}"

        # Prevent reuse when usage_limit == 1
        if self.usage_limit == 1 and CouponUsage.objects.filter(coupon=self, user=user).exists():
            return False, "You have already used this coupon"

        code = (self.code or '').upper()
        now = timezone.now()

        # SWEETBIRTHDAY: 25% off on user's birthday only
        if code == 'SWEETBIRTHDAY':
            try:
                profile = user.userprofile
                if not profile.birth_date:
                    return False, "Add your birth date in profile to use this coupon"
                today = now.date()
                if not (profile.birth_date.month == today.month and profile.birth_date.day == today.day):
                    return False, "Offer not applicable"
            except UserProfile.DoesNotExist:
                return False, "Add your birth date in profile to use this coupon"

        # WELCOME10: 10% off on first purchase
        if code == 'WELCOME10':
            if Order.objects.filter(user=user).exists():
                return False, "WELCOME10 is only for your first purchase"

        # FREESHIP: Free shipping on orders above 1000 (no subtotal discount; shipping waived in checkout)
        if code == 'FREESHIP':
            if order_amount < 1000:
                return False, "FREESHIP applies on orders of ₹1000 or more"

        # CHOCOLATEISLIFE: 5% off anytime -> no extra checks

        # MIDNIGHTMUNCH: 10% off orders placed between 10 PM – 2 AM
        if code == 'MIDNIGHTMUNCH':
            hour = now.astimezone(timezone.get_current_timezone()).time().hour
            if not (hour >= 22 or hour < 2):
                return False, "MIDNIGHTMUNCH is valid 10 PM – 2 AM"

        return True, "Coupon is valid"

    def calculate_discount(self, order_amount):
        """Calculate discount amount for given order amount"""
        if self.discount_type == 'percentage':
            discount = (order_amount * self.discount_value) / 100
            if self.maximum_discount_amount:
                discount = min(discount, self.maximum_discount_amount)
        else:
            discount = self.discount_value
        
        return min(discount, order_amount)  # Discount cannot exceed order amount

    def use_coupon(self, user, order):
        """Mark coupon as used and create usage record"""
        self.used_count += 1
        self.save()
        
        CouponUsage.objects.create(
            coupon=self,
            user=user,
            order=order,
            discount_amount=self.calculate_discount(order.total_price())
        )

class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['coupon', 'user', 'order']

    def __str__(self):
        return f"{self.user.username} used {self.coupon.code} - ₹{self.discount_amount}"


# --- Returns & Notifications ---
class ReturnRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        DECLINED = 'declined', 'Declined'

    REASON_CHOICES = [
        ('wrong_product', 'Wrong product received'),
        ('damaged_item', 'Damaged item received'),
        ('defective_product', 'Defective product'),
        ('item_missing', 'Item missing from package'),
        ('cancelled_before_dispatch', 'Order cancelled before dispatch'),
        ('rejected_at_delivery', 'Order rejected at delivery'),
        ('out_of_stock', 'Product out of stock after order confirmation'),
        ('lost_in_transit', 'Shipment lost in transit'),
        ('wrong_variant', 'Received wrong variant'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    reason_other = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_returns')

    def __str__(self):
        return f"Return {self.id} - {self.order.invoice_number} - {self.status}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username} - {'read' if self.is_read else 'unread'}"
