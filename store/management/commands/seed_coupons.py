from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from store.models import Coupon


class Command(BaseCommand):
    help = "Seed default coupon codes: SWEETBIRTHDAY, WELCOME10, FREESHIP, CHOCOLATEISLIFE, MIDNIGHTMUNCH"

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Overwrite existing coupon settings')
        parser.add_argument('--valid-days', type=int, default=365, help='Validity from now in days')

    def handle(self, *args, **options):
        User = get_user_model()
        now = timezone.now()
        valid_until = now + timezone.timedelta(days=options['valid_days'])
        force = options['force']

        # Pick a creator: prefer superuser, then any staff, then any user
        creator = User.objects.filter(is_superuser=True).first()
        if not creator:
            creator = User.objects.filter(is_staff=True).first()
        if not creator:
            creator = User.objects.first()
        if not creator:
            self.stderr.write(self.style.ERROR("No users found. Please create an admin/user before seeding coupons."))
            return

        seeds = [
            {
                'code': 'SWEETBIRTHDAY',
                'description': '25% OFF on your birthday only',
                'discount_type': 'percentage',
                'discount_value': 25,
                'minimum_order_amount': 0,
                'maximum_discount_amount': None,
                'usage_limit': None,
            },
            {
                'code': 'WELCOME10',
                'description': '10% OFF on first purchase',
                'discount_type': 'percentage',
                'discount_value': 10,
                'minimum_order_amount': 0,
                'maximum_discount_amount': None,
                'usage_limit': 1,  # optional; logic also enforces first purchase
            },
            {
                'code': 'FREESHIP',
                'description': 'Free shipping on orders ≥ ₹1000',
                'discount_type': 'percentage',
                'discount_value': 0,  # discount applied to shipping in checkout
                'minimum_order_amount': 1000,
                'maximum_discount_amount': None,
                'usage_limit': None,
            },
            {
                'code': 'CHOCOLATEISLIFE',
                'description': '5% OFF for chocolate lovers (anytime)',
                'discount_type': 'percentage',
                'discount_value': 5,
                'minimum_order_amount': 0,
                'maximum_discount_amount': None,
                'usage_limit': None,
            },
            {
                'code': 'MIDNIGHTMUNCH',
                'description': '10% OFF for orders between 10 PM – 2 AM',
                'discount_type': 'percentage',
                'discount_value': 10,
                'minimum_order_amount': 0,
                'maximum_discount_amount': None,
                'usage_limit': None,
            },
        ]

        created = 0
        updated = 0
        for s in seeds:
            code = s['code']
            coupon, was_created = Coupon.objects.get_or_create(code=code, defaults={
                'description': s['description'],
                'discount_type': s['discount_type'],
                'discount_value': s['discount_value'],
                'minimum_order_amount': s['minimum_order_amount'],
                'maximum_discount_amount': s['maximum_discount_amount'],
                'usage_limit': s['usage_limit'],
                'used_count': 0,
                'is_active': True,
                'valid_from': now,
                'valid_until': valid_until,
                'created_by': creator,
            })

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created coupon {code}"))
            else:
                if force:
                    coupon.description = s['description']
                    coupon.discount_type = s['discount_type']
                    coupon.discount_value = s['discount_value']
                    coupon.minimum_order_amount = s['minimum_order_amount']
                    coupon.maximum_discount_amount = s['maximum_discount_amount']
                    coupon.usage_limit = s['usage_limit']
                    coupon.is_active = True
                    coupon.valid_from = now
                    coupon.valid_until = valid_until
                    if not coupon.created_by_id:
                        coupon.created_by = creator
                    coupon.save()
                    updated += 1
                    self.stdout.write(self.style.WARNING(f"Updated coupon {code}"))
                else:
                    self.stdout.write(f"Coupon {code} already exists. Use --force to update.")

        self.stdout.write(self.style.SUCCESS(f"Seeding complete. Created: {created}, Updated: {updated}"))
