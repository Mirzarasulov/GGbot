from django.contrib import admin
from .models import Product, Order, Cart, UserProfile

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'price', 'stock', 'is_active', 'created_at']
    list_editable = ['price', 'stock', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['-created_at']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user_name', 'phone', 'total_amount', 'status', 'created_at']
    list_editable = ['status']
    list_filter = ['status', 'created_at']
    search_fields = ['order_id', 'user_name', 'phone']
    ordering = ['-created_at']
    readonly_fields = ['order_id', 'created_at']

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'telegram_id', 'session_key', 'items_count', 'updated_at']
    search_fields = ['telegram_id', 'session_key']
    
    def items_count(self, obj):
        return len(obj.items)
    items_count.short_description = 'Товаров'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'first_name', 'phone', 'total_orders', 'total_spent', 'created_at']
    search_fields = ['telegram_id', 'first_name', 'username', 'phone']
    ordering = ['-created_at']