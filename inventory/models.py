from django.db import models

# Create your models here.
class ProductInventory(models.Model):
    sku = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name