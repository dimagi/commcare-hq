from django.db import models
import uuid


class Product(models.Model):
    name = models.CharField(max_length=30)
    product_type = models.CharField(max_length=50)
    price = models.IntegerField(max_length=20)

    def __str__(self):
        return self.name


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    #product = models.ForeignKey(Product)

    def __str__(self):
        return self.id