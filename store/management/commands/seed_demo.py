import os
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from store.models import Chocolate, Coupon


class Command(BaseCommand):
    help = "Load the demo catalog and demo accounts into an empty database."

    def handle(self, *args, **options):
        if Chocolate.objects.exists():
            self.stdout.write("Demo data already present, skipping.")
            self.refresh_coupons()
            return
        admin, _ = User.objects.get_or_create(pk=1, defaults={"username": "admin", "is_staff": True, "is_superuser": True})
        admin.set_password(os.getenv("DEMO_ADMIN_PASSWORD", "admin12345"))
        admin.save()
        demo, _ = User.objects.get_or_create(username="demo")
        demo.set_password(os.getenv("DEMO_USER_PASSWORD", "demo12345"))
        demo.save()
        call_command("loaddata", "demo_data")
        self.refresh_coupons()
        self.stdout.write(self.style.SUCCESS("Demo data loaded."))

    def refresh_coupons(self):
        now = timezone.now()
        Coupon.objects.update(valid_from=now - timedelta(days=1), valid_until=now + timedelta(days=365), is_active=True)
