import os
import sys
import django
import logging
from datetime import datetime
import json
import re

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shop_bot.settings')
django.setup()

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from bot.models import Product, Order, Cart, UserProfile

# ============ КОНФИГУРАЦИЯ ============
BOT_TOKEN = "8954981282:AAFPuBkSQCqXfMWCtUyFfDIsVp0HhlarZLw"
GROUP_ID = -1004318807187

bot = telebot.TeleBot(BOT_TOKEN)
logger = logging.getLogger(__name__)

# Хранилище данных пользователей
user_data = {}

def format_price(price):
    return f"{int(price):,}".replace(',', ' ')

def get_location_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(KeyboardButton("📍 Отправить локацию", request_location=True))
    keyboard.add(KeyboardButton("❌ Отмена"))
    return keyboard

def get_phone_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(KeyboardButton("📱 Отправить номер", request_contact=True))
    keyboard.add(KeyboardButton("✏️ Ввести вручную"))
    keyboard.add(KeyboardButton("❌ Отмена"))
    return keyboard

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🛍️ Каталог товаров", url="http://127.0.0.1:8000/shop/"),
        InlineKeyboardButton("🛒 Корзина", url="http://127.0.0.1:8000/cart/"),
        InlineKeyboardButton("📋 Мои заказы", callback_data="my_orders"),
        InlineKeyboardButton("📍 Моя локация", callback_data="my_location"),
        InlineKeyboardButton("📝 Обновить данные", callback_data="update_profile"),
        InlineKeyboardButton("ℹ️ Помощь", callback_data="help")
    )
    return keyboard

# ============ КОМАНДА СТАРТ ============
@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    
    # Очищаем старые данные
    if user.id in user_data:
        del user_data[user.id]
    
    # Создаем или получаем профиль
    profile, created = UserProfile.objects.get_or_create(
        telegram_id=user.id,
        defaults={
            'username': user.username or '',
            'first_name': user.first_name or 'Пользователь'
        }
    )
    
    # Заполняем данные из профиля
    user_data[user.id] = {
        'name': profile.first_name or '',
        'phone': profile.phone or '',
        'address': profile.address or '',
        'location': profile.location or '',
        'location_lat': profile.location_lat or '',
        'location_lng': profile.location_lng or '',
        'step': 'location'
    }
    
    text = f"""
🚴‍♂️ *Velosher Shop*

Здравствуйте, {user.first_name}! 👋

📍 *Шаг 1/3: Отправьте локацию*
Нажмите кнопку 📍 ниже
"""
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=get_location_keyboard()
    )

# ============ ОБРАБОТКА ЛОКАЦИИ ============
@bot.message_handler(content_types=['location'])
def handle_location(message):
    user_id = message.from_user.id
    location = message.location
    
    if user_id not in user_data:
        user_data[user_id] = {'step': 'location'}
    
    # Сохраняем локацию
    user_data[user_id]['location'] = f"{location.latitude}, {location.longitude}"
    user_data[user_id]['location_lat'] = str(location.latitude)
    user_data[user_id]['location_lng'] = str(location.longitude)
    user_data[user_id]['step'] = 'name'
    
    # Сохраняем в профиль
    profile, _ = UserProfile.objects.get_or_create(telegram_id=user_id)
    profile.location_lat = str(location.latitude)
    profile.location_lng = str(location.longitude)
    profile.location = f"{location.latitude}, {location.longitude}"
    profile.save()
    
    map_link = f"https://maps.google.com/maps?q={location.latitude},{location.longitude}"
    
    bot.reply_to(
        message,
        f"✅ Локация получена!\n\n"
        f"📝 *Шаг 2/3: Ваше имя*\n"
        f"Введите ваше имя:",
        parse_mode='Markdown'
    )

# ============ ОБРАБОТКА ИМЕНИ ============
@bot.message_handler(func=lambda message: message.text and message.text not in ["❌ Отмена"])
def handle_name(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {'step': 'name'}
    
    if user_data[user_id].get('step') == 'name':
        user_data[user_id]['name'] = message.text
        user_data[user_id]['step'] = 'phone'
        
        text = f"""
✅ Имя сохранено!

📱 *Шаг 3/3: Ваш телефон*
Отправьте номер или введите вручную:
"""
        bot.reply_to(message, text, parse_mode='Markdown', reply_markup=get_phone_keyboard())
        return
    
    # Если шаг phone
    if user_data[user_id].get('step') == 'phone':
        handle_phone(message)
        return

# ============ ОБРАБОТКА ТЕЛЕФОНА ============
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user_id = message.from_user.id
    contact = message.contact
    
    if user_id not in user_data:
        user_data[user_id] = {'step': 'phone'}
    
    if user_data[user_id].get('step') == 'phone':
        user_data[user_id]['phone'] = contact.phone_number
        user_data[user_id]['step'] = 'complete'
        
        # Сохраняем в профиль
        profile, _ = UserProfile.objects.get_or_create(telegram_id=user_id)
        profile.phone = contact.phone_number
        profile.first_name = user_data[user_id].get('name', profile.first_name)
        profile.save()
        
        show_complete_profile(message)
        return

def handle_phone(message):
    user_id = message.from_user.id
    phone = message.text.strip()
    
    if phone == "❌ Отмена":
        cancel_registration(message)
        return
    
    if phone == "✏️ Ввести вручную":
        bot.reply_to(message, "📱 Введите номер телефона:")
        return
    
    # Простая проверка
    phone_clean = re.sub(r'[^0-9+]', '', phone)
    if len(phone_clean) < 10:
        bot.reply_to(message, "❌ Неверный формат!\nПопробуйте еще раз:")
        return
    
    user_data[user_id]['phone'] = phone_clean
    user_data[user_id]['step'] = 'complete'
    
    # Сохраняем в профиль
    profile, _ = UserProfile.objects.get_or_create(telegram_id=user_id)
    profile.phone = phone_clean
    profile.first_name = user_data[user_id].get('name', profile.first_name)
    profile.save()
    
    show_complete_profile(message)

# ============ ПОКАЗАТЬ ВСЕ ДАННЫЕ ============
def show_complete_profile(message):
    user_id = message.from_user.id
    data = user_data[user_id]
    
    map_link = ""
    if data.get('location_lat') and data.get('location_lng'):
        map_link = f"https://maps.google.com/maps?q={data['location_lat']},{data['location_lng']}"
    
    text = f"""
✅ *Все данные получены!* 🎉

👤 *Имя:* {data.get('name', 'Не указано')}
📱 *Телефон:* {data.get('phone', 'Не указан')}
📍 *Локация:* {data.get('location', 'Не указана')}
{'🗺️ [Открыть на карте](' + map_link + ')' if map_link else ''}

❓ *Всё верно?*
"""
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да, всё верно", callback_data="save_profile"),
        InlineKeyboardButton("✏️ Исправить", callback_data="edit_profile")
    )
    keyboard.add(
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_profile")
    )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# ============ СОХРАНЕНИЕ ============
@bot.callback_query_handler(func=lambda call: call.data == "save_profile")
def save_profile(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    
    if user_id not in user_data:
        bot.send_message(call.message.chat.id, "❌ Ошибка! Нажмите /start")
        return
    
    data = user_data[user_id]
    
    # Обновляем профиль
    profile, _ = UserProfile.objects.get_or_create(telegram_id=user_id)
    profile.first_name = data.get('name', profile.first_name)
    profile.phone = data.get('phone', profile.phone)
    profile.address = data.get('address', profile.address)
    profile.location = data.get('location', profile.location)
    profile.location_lat = data.get('location_lat', profile.location_lat)
    profile.location_lng = data.get('location_lng', profile.location_lng)
    profile.save()
    
    # ОТПРАВЛЯЕМ В ГРУППУ
    send_to_group(user_id, data, call.from_user)
    
    # Очищаем данные
    del user_data[user_id]
    
    text = f"""
✅ *Профиль сохранен!* 🎉

📍 *Ваши данные сохранены.*

🛍️ *Что дальше?*
• Перейдите в каталог товаров
• Оформите заказ

📱 *Сайт:* http://127.0.0.1:8000/shop/
"""
    bot.send_message(
        call.message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )

# ============ ОТПРАВКА В ГРУППУ ============
def send_to_group(user_id, data, user):
    try:
        map_link = ""
        if data.get('location_lat') and data.get('location_lng'):
            map_link = f"https://maps.google.com/maps?q={data['location_lat']},{data['location_lng']}"
        
        text = f"""
🆕 *НОВЫЙ ПОЛЬЗОВАТЕЛЬ* 🎉

👤 *Имя:* {data.get('name', 'Не указано')}
🆔 ID: {user.id}
👤 @{user.username or 'не указан'}

📱 *Телефон:* {data.get('phone', 'Не указан')}
📍 *Локация:* {data.get('location', 'Не указана')}
{'🗺️ [Открыть на карте](' + map_link + ')' if map_link else ''}

📅 *Дата:* {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
        bot.send_message(GROUP_ID, text, parse_mode='Markdown')
        print(f"✅ Данные отправлены в группу")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

# ============ ИСПРАВИТЬ ============
@bot.callback_query_handler(func=lambda call: call.data == "edit_profile")
def edit_profile(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    
    if user_id in user_data:
        user_data[user_id]['step'] = 'name'
        text = "✏️ *Введите ваше имя заново:*"
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ============ ОТМЕНА ============
@bot.callback_query_handler(func=lambda call: call.data == "cancel_profile")
def cancel_profile(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    text = "❌ *Отменено*\n\nНажмите /start для начала"
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "❌ Отмена")
def cancel_registration(message):
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    text = "❌ *Отменено*\n\nНажмите /start для начала"
    bot.reply_to(message, text, parse_mode='Markdown')

# ============ КНОПКИ ============
@bot.callback_query_handler(func=lambda call: call.data == "my_orders")
def my_orders(call):
    bot.answer_callback_query(call.id)
    orders = Order.objects.filter(telegram_id=call.from_user.id).order_by('-created_at')[:10]
    
    if not orders:
        bot.send_message(call.message.chat.id, "📋 *У вас пока нет заказов*", parse_mode='Markdown')
        return
    
    text = "📋 *Ваши заказы:*\n\n"
    for order in orders:
        status_emoji = {
            'pending': '⏳',
            'paid': '✅',
            'shipped': '🚚',
            'delivered': '📦',
            'cancelled': '❌'
        }.get(order.status, '❓')
        
        text += f"{status_emoji} *Заказ #{order.order_id}*\n"
        text += f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        text += f"👤 {order.user_name}\n"
        text += f"💰 {format_price(order.total_amount)} сум\n"
        text += f"📦 {order.get_status_display()}\n\n"
    
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "my_location")
def my_location(call):
    bot.answer_callback_query(call.id)
    try:
        profile = UserProfile.objects.get(telegram_id=call.from_user.id)
        if profile.location_lat and profile.location_lng:
            map_link = f"https://maps.google.com/maps?q={profile.location_lat},{profile.location_lng}"
            text = f"📍 [Открыть на карте]({map_link})"
        else:
            text = "📍 *У вас нет сохраненной локации*\n\nНажмите /start для обновления"
    except:
        text = "❌ Ошибка! Нажмите /start"
    
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "update_profile")
def update_profile(call):
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "📝 *Обновление данных*\n\nНажмите /start чтобы обновить профиль",
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "help")
def help_command(call):
    bot.answer_callback_query(call.id)
    text = """
ℹ️ *Помощь*

*Регистрация:*
1. Нажмите /start
2. Отправьте локацию 📍
3. Введите имя 👤
4. Введите телефон 📱
5. Подтвердите ✅

*После регистрации:*
🛍️ Каталог товаров
🛒 Корзина
📋 Мои заказы
📍 Моя локация

💳 *Оплата:* Перевод на карту
🚚 *Доставка:* По всему Узбекистану

📞 *Контакты:* +998 90 123 45 67
"""
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

# ============ НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ============
@bot.message_handler(func=lambda message: True)
def unknown_message(message):
    if message.text and message.text.startswith('/'):
        return
    bot.reply_to(message, "❓ Неизвестная команда. Нажмите /start")

# ============ ЗАПУСК ============
if __name__ == '__main__':
    print("=" * 50)
    print("🤖 Velosher Shop Бот запущен!")
    print("📋 Сбор данных: Локация → Имя → Телефон")
    print("🚀 Нажмите Ctrl+C для остановки")
    print("=" * 50)
    
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"❌ Ошибка: {e}")