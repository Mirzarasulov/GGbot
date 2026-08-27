from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # Страницы магазина
    path('', views.shop_page, name='shop'),
    path('shop/', views.shop_page, name='shop'),
    path('shop/<int:product_id>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_page, name='cart'),
    path('checkout/', views.checkout_page, name='checkout'),
    
    # API - Товары
    path('api/products/', views.get_products, name='get_products'),
    path('api/products/<int:product_id>/', views.get_product_detail, name='get_product_detail'),
    
    # API - Корзина
    path('api/cart/', views.get_cart, name='get_cart'),
    path('api/cart/add/', views.add_to_cart, name='add_to_cart'),
    path('api/cart/update/', views.update_cart_item, name='update_cart_item'),
    path('api/cart/clear/', views.clear_cart, name='clear_cart'),
    
    # API - Заказы
    path('api/order/create/', views.create_order, name='create_order'),
    
    # API - Статистика и заказы (для админки)
    path('api/stats/', views.get_stats, name='get_stats'),
    path('api/orders/', views.get_orders, name='get_orders'),
    
    # API - Админка (управление товарами)
    path('api/admin/products/', views.get_products_admin, name='get_products_admin'),
    path('api/admin/products/add/', views.add_product_admin, name='add_product_admin'),
    path('api/admin/products/<int:product_id>/delete/', views.delete_product_admin, name='delete_product_admin'),
    path('api/admin/users/', views.get_users_admin, name='get_users_admin'),
    
    # ========== ТЕСТОВАЯ ОТПРАВКА В TELEGRAM ==========
    path('api/test-telegram/', views.test_telegram, name='test_telegram'),  # ДОБАВЛЯЕМ
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)