from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from django.utils import timezone
import json
import os
import requests

from .models import Product, Order, Cart, UserProfile

# ============ КОНФИГУРАЦИЯ TELEGRAM ============
BOT_TOKEN = "8954981282:AAFPuBkSQCqXfMWCtUyFfDIsVp0HhlarZLw"
GROUP_ID = -1004318807187  # НОВЫЙ ID СУПЕРГРУППЫ!

# ============ СТРАНИЦЫ ============

def shop_page(request):
    return render(request, 'shop/shop.html')

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    product.views += 1
    product.save()
    return render(request, 'shop/product_detail.html', {'product': product})

def cart_page(request):
    return render(request, 'shop/cart.html')

def checkout_page(request):
    return render(request, 'shop/checkout.html')

# ============ API - ТОВАРЫ ============

def get_products(request):
    products = Product.objects.filter(is_active=True)
    data = []
    for p in products:
        data.append({
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'price': float(p.price),
            'price_format': p.price_format,
            'old_price': float(p.old_price) if p.old_price else None,
            'discount': p.discount,
            'stock': p.stock,
            'image': p.image.url if p.image else '',
            'category': p.category,
            'in_stock': p.stock > 0,
            'views': p.views,
        })
    return JsonResponse({'products': data})

def get_product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    return JsonResponse({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'price': float(product.price),
        'price_format': product.price_format,
        'old_price': float(product.old_price) if product.old_price else None,
        'discount': product.discount,
        'stock': product.stock,
        'image': product.image.url if product.image else '',
        'category': product.category,
        'in_stock': product.stock > 0,
        'views': product.views,
    })

# ============ API - КОРЗИНА ============

def get_cart(request):
    cart = request.session.get('cart', [])
    total = 0
    for item in cart:
        item['subtotal'] = item['price'] * item['quantity']
        item['subtotal_format'] = f"{int(item['subtotal']):,}".replace(',', ' ')
        total += item['subtotal']
    
    return JsonResponse({
        'items': cart,
        'total': total,
        'total_format': f"{int(total):,}".replace(',', ' '),
        'count': sum(item['quantity'] for item in cart)
    })

@csrf_exempt
def add_to_cart(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        product = get_object_or_404(Product, id=product_id)
        cart = request.session.get('cart', [])
        
        found = False
        for item in cart:
            if item['id'] == product_id:
                item['quantity'] += quantity
                found = True
                break
        
        if not found:
            cart.append({
                'id': product_id,
                'name': product.name,
                'price': float(product.price),
                'quantity': quantity,
                'image': product.image.url if product.image else ''
            })
        
        request.session['cart'] = cart
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': f'{product.name} добавлен в корзину',
            'count': len(cart)
        })
    return JsonResponse({'error': 'POST required'}, status=400)

@csrf_exempt
def update_cart_item(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        cart = request.session.get('cart', [])
        for item in cart:
            if item['id'] == product_id:
                if quantity <= 0:
                    cart = [i for i in cart if i['id'] != product_id]
                else:
                    item['quantity'] = quantity
                break
        
        request.session['cart'] = cart
        request.session.modified = True
        
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)

@csrf_exempt
def clear_cart(request):
    if request.method == 'POST':
        request.session['cart'] = []
        request.session.modified = True
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST required'}, status=400)

# ============ API - ЗАКАЗЫ ============

@csrf_exempt
def create_order(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        cart = request.session.get('cart', [])
        
        if not cart:
            return JsonResponse({'error': 'Корзина пуста'}, status=400)
        
        total = sum(item['price'] * item['quantity'] for item in cart)
        
        order = Order.objects.create(
            user_name=data.get('user_name', 'Гость'),
            phone=data.get('phone', ''),
            address=data.get('address', 'Адрес указан в Telegram'),
            products=cart,
            total_amount=total,
            status='pending'
        )
        
        # Отправка в Telegram
        send_order_to_telegram(order, cart, total)
        
        # Очищаем корзину
        request.session['cart'] = []
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'order_id': order.order_id,
            'total': float(total),
            'total_format': f"{int(total):,}".replace(',', ' ')
        })
    return JsonResponse({'error': 'POST required'}, status=400)

# ============ ОТПРАВКА В TELEGRAM ============

def send_order_to_telegram(order, cart, total):
    """Отправить информацию о заказе в Telegram группу"""
    try:
        text = f"""
🆕 *НОВЫЙ ЗАКАЗ #{order.order_id}*

👤 *Покупатель:* {order.user_name}
📱 *Телефон:* {order.phone}
📍 *Адрес:* {order.address}

📦 *Товары:*
"""
        for item in cart:
            text += f"• {item['name']} × {item['quantity']} = {int(item['price'] * item['quantity']):,} сум\n".replace(',', ' ')
        
        text += f"""
💰 *Итого:* {int(total):,} сум

📅 *Дата:* {timezone.now().strftime('%d.%m.%Y %H:%M')}
📌 *Статус:* ⏳ Ожидает оплаты
"""
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': GROUP_ID,  # -1004318807187
            'text': text,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, data=payload)
        
        if response.status_code == 200:
            print(f"✅ Заказ #{order.order_id} отправлен в Telegram")
        else:
            print(f"❌ Ошибка отправки: {response.text}")
            
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")

# ============ ТЕСТОВАЯ ОТПРАВКА ============

def test_telegram(request):
    """Тестовая отправка сообщения в Telegram"""
    try:
        text = """
🧪 *ТЕСТОВОЕ СООБЩЕНИЕ*

Бот работает и может отправлять сообщения в эту группу!

✅ *Проверка успешна*
📅 *Дата:* {}
""".format(timezone.now().strftime('%d.%m.%Y %H:%M'))
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': GROUP_ID,  # -1004318807187
            'text': text,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, data=payload)
        
        if response.status_code == 200:
            return JsonResponse({'success': True, 'message': 'Сообщение отправлено в Telegram'})
        else:
            return JsonResponse({'success': False, 'error': response.text}, status=500)
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ============ API - СТАТИСТИКА ============

def get_stats(request):
    users = UserProfile.objects.count()
    orders = Order.objects.count()
    revenue = Order.objects.filter(status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
    today = timezone.now().date()
    
    return JsonResponse({
        'users': users,
        'orders': orders,
        'revenue': float(revenue),
        'revenue_format': f"{int(revenue):,}".replace(',', ' '),
        'todayOrders': Order.objects.filter(created_at__date=today).count(),
        'pending_orders': Order.objects.filter(status='pending').count(),
        'paid_orders': Order.objects.filter(status='paid').count(),
    })

def get_orders(request):
    orders = Order.objects.all().order_by('-created_at')
    data = []
    for order in orders:
        data.append({
            'id': order.id,
            'order_id': order.order_id,
            'user_name': order.user_name,
            'phone': order.phone,
            'address': order.address,
            'total_amount': float(order.total_amount),
            'total_format': f"{int(order.total_amount):,}".replace(',', ' '),
            'status': order.status,
            'status_display': dict(Order.STATUS_CHOICES).get(order.status, order.status),
            'created_at': order.created_at.strftime('%d.%m.%Y %H:%M'),
            'products': order.products,
        })
    return JsonResponse({'orders': data})

# ============ API - АДМИНКА ============

def get_products_admin(request):
    products = Product.objects.all()
    data = []
    for p in products:
        data.append({
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'price': float(p.price),
            'price_format': p.price_format,
            'stock': p.stock,
            'image': p.image.url if p.image else '',
            'category': p.category,
            'is_active': p.is_active,
            'views': p.views,
        })
    return JsonResponse({'products': data})

@csrf_exempt
def add_product_admin(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        stock = request.POST.get('stock', 10)
        image = request.FILES.get('image')
        
        product = Product.objects.create(
            name=name,
            description=description,
            price=price,
            stock=stock,
        )
        if image:
            product.image = image
            product.save()
        
        return JsonResponse({'success': True, 'id': product.id}, status=201)
    return JsonResponse({'error': 'POST required'}, status=400)

@csrf_exempt
def delete_product_admin(request, product_id):
    if request.method == 'DELETE':
        product = Product.objects.get(id=product_id)
        if product.image and os.path.isfile(product.image.path):
            os.remove(product.image.path)
        product.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'DELETE required'}, status=400)

def get_users_admin(request):
    users = UserProfile.objects.all().order_by('-created_at')
    data = []
    for u in users:
        data.append({
            'id': u.id,
            'telegram_id': u.telegram_id,
            'username': u.username,
            'first_name': u.first_name,
            'phone': u.phone,
            'address': u.address,
            'total_orders': u.total_orders,
            'total_spent': float(u.total_spent),
            'total_spent_format': f"{int(u.total_spent):,}".replace(',', ' '),
            'created_at': u.created_at.strftime('%d.%m.%Y %H:%M'),
        })
    return JsonResponse({'users': data})