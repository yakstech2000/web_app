from django.contrib import admin
from .models import(
Product,
Brand,
Category,
Customer,
Order,
Review
)
admin.site.register(Product)
admin.site.register(Brand)
admin.site.register(Category)
admin.site.register(Customer)
admin.site.register(Order)
admin.site.register(Review)
# Register your models here.
