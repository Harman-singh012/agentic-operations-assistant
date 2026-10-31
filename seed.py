import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from inventory.models import ProductInventory as P

P.objects.all().delete()
P.objects.create(sku="TP-X1", name="ThinkPad X1 Carbon", category="Laptop", quantity=15, price=1499)
P.objects.create(sku="TP-T14", name="ThinkPad T14", category="Laptop", quantity=0, price=1099)
P.objects.create(sku="LG-5", name="Legion 5", category="Gaming Laptop", quantity=8, price=1299)
P.objects.create(sku="IP-3", name="IdeaPad 3", category="Laptop", quantity=40, price=549)
print("Seeded:", P.objects.count(), "products")