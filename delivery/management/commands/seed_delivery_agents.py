from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from delivery.models import DeliveryAgent, Vehicle
from stock_and_location.models import StoreLocation

AGENTS = [
    {"name": "Rajesh Patel", "email": "rajesh.patel87@example.com", "phone": "+919825341765", "username": "Rajesh", "state": "Gujarat", "bike": "GJ 01 AB 4598"},
    {"name": "Kunal Desai", "email": "kunal.desai26@example.com", "phone": "+919725341890", "username": "Kunal", "state": "Gujarat", "bike": "GJ 05 CN 8324"},
    {"name": "Manish Shah", "email": "manish.shah43@example.com", "phone": "+919898743251", "username": "Manish", "state": "Gujarat", "bike": "GJ 18 QT 6245"},
    {"name": "Rohit More", "email": "rohit.more92@example.com", "phone": "+919930785412", "username": "Rohit", "state": "Maharashtra", "bike": "MH 12 ZX 2384"},
    {"name": "Ajay Kulkarni", "email": "ajay.kulkarni38@example.com", "phone": "+919821456730", "username": "Ajay", "state": "Maharashtra", "bike": "MH 14 PL 6542"},
    {"name": "Sameer Joshi", "email": "sameer.joshi55@example.com", "phone": "+919867541230", "username": "Sameer", "state": "Maharashtra", "bike": "MH 01 DR 9125"},
    {"name": "Suresh Singh", "email": "suresh.singh71@example.com", "phone": "+919829023145", "username": "Suresh", "state": "Rajasthan", "bike": "RJ 14 MF 7482"},
    {"name": "Akash Sharma", "email": "akash.sharma20@example.com", "phone": "+919929541873", "username": "Akash", "state": "Rajasthan", "bike": "RJ 27 BM 5362"},
    {"name": "Rakesh Choudhary", "email": "rakesh.choudhary64@example.com", "phone": "+919982647310", "username": "Rakesh", "state": "Rajasthan", "bike": "RJ 09 TR 8294"},
    {"name": "Anil Kumar", "email": "anil.kumar57@example.com", "phone": "+919845123067", "username": "Anil", "state": "Karnataka", "bike": "KA 01 XP 4725"},
    {"name": "Manjunath Gowda", "email": "manjunath.gowda31@example.com", "phone": "+919880456213", "username": "Manjunath", "state": "Karnataka", "bike": "KA 03 CN 9834"},
    {"name": "Raghav Shetty", "email": "raghav.shetty44@example.com", "phone": "+919901458320", "username": "Raghav", "state": "Karnataka", "bike": "KA 05 GY 7642"},
    {"name": "Arjun Mehta", "email": "arjun.mehta16@example.com", "phone": "+919874563210", "username": "Arjun", "state": "Delhi", "bike": "DL 05 AB 4932"},
    {"name": "Vikram Malhotra", "email": "vikram.malhotra81@example.com", "phone": "+919998765432", "username": "Vikram", "state": "Delhi", "bike": "DL 08 PL 7483"},
    {"name": "Amit Khanna", "email": "amit.khanna22@example.com", "phone": "+919812345670", "username": "Amit", "state": "Delhi", "bike": "DL 01 DR 8251"},
]

class Command(BaseCommand):
    help = "Seed delivery agents with state-matched vehicles and store locations. Vehicles and Stores must already exist."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Validate and show actions without saving")

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options.get("dry_run")
        created, skipped = 0, 0

        # Build quick lookup for stores by state (prefer active)
        stores_by_state = {}
        for store in StoreLocation.objects.all().order_by("-is_active", "name"):
            key = (store.state or "").strip().lower()
            # Only keep stores that are not already assigned to an agent (OneToOne)
            if getattr(store, "delivery_agent", None) is None and key:
                stores_by_state.setdefault(key, []).append(store)

        # Vehicles by state, only unassigned
        vehicles_by_state = {}
        for v in Vehicle.objects.filter(agent__isnull=True, is_active=True):
            key = (v.state or "").strip().lower()
            if key:
                vehicles_by_state.setdefault(key, []).append(v)

        for entry in AGENTS:
            name = entry["name"]
            email = entry["email"]
            phone = entry["phone"]
            username = entry["username"]
            state = (entry["state"] or "").strip().lower()
            bike_number = entry["bike"].strip()

            if DeliveryAgent.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f"Skip existing agent @{username}"))
                skipped += 1
                continue

            # Pick a store for this state
            store = None
            if state in stores_by_state and stores_by_state[state]:
                store = stores_by_state[state].pop(0)
            else:
                raise CommandError(f"No available StoreLocation for state '{entry['state']}'. Create one and try again.")

            # Find vehicle by exact plate in same state and unused
            vehicle = Vehicle.objects.filter(number=bike_number, state__iexact=entry["state"]).first()
            if not vehicle:
                raise CommandError(f"Vehicle '{bike_number}' for state '{entry['state']}' not found.")
            if getattr(vehicle, "agent", None) is not None:
                raise CommandError(f"Vehicle '{bike_number}' already assigned to another agent.")

            agent = DeliveryAgent(
                name=name,
                email=email,
                phone_number=phone,
                username=username,
                is_active=True,
                is_available=True,
                assigned_vehicle=vehicle,
                store_location=store,
            )

            # Let model-level validation enforce state match
            agent.full_clean()

            if dry:
                self.stdout.write(self.style.NOTICE(f"Would create agent {name} (@{username}) -> {entry['state']}: {vehicle.number} / {store.name}"))
            else:
                agent.save()
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created agent {name} (@{username})"))

        if dry:
            raise CommandError("Dry-run complete (no changes saved). Rerun without --dry-run to persist.")

        self.stdout.write(self.style.SUCCESS(f"Done. Created={created}, Skipped={skipped}"))
