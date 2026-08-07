from typing import Any

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Brand(models.Model):
    """Store brand information"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Brands"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Category(models.Model):
    """Store product categories"""
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Store product information"""
    name = models.CharField(max_length=255)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    description = models.TextField(help_text="Write full product specifications (RAM, Storage, Battery, Color, etc.)")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(validators=[MinValueValidator(0)])

    # Product Images
    product_image = models.ImageField(upload_to='products/images/')
    product_image_2 = models.ImageField(upload_to='products/images/', blank=True, null=True)
    product_image_3 = models.ImageField(upload_to='products/images/', blank=True, null=True)

    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['brand', 'category']),
            models.Index(fields=['is_available']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        """Check if product stock is low (less than 10)"""
        return self.stock_quantity < 10


class Customer(models.Model):
    """Store customer information (created automatically on user registration)"""
    #user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ['-created_at']

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(args, kwargs)
        self.orders = None

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def total_orders(self):
        """Get total number of orders"""
        return self.orders.count()

    @property
    def total_spent(self):
        """Get total amount spent"""
        return sum(order.total_amount for order in self.orders.all())


class Order(models.Model):
    """Store order information (created automatically on checkout)"""
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=50, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    shipping_address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.order_number}"


class Review(models.Model):
    """Store product reviews (created automatically by customers)"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review_text = models.TextField()
    review_image = models.ImageField(upload_to='reviews/images/', blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ['-created_at']
        unique_together = ('customer', 'product')

    def __str__(self):
        return f"Review by {self.customer} for {self.product}"

