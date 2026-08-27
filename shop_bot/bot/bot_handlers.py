# bot/bot_handlers.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shop_bot.settings')
django.setup()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from .models import Product, Order, Cart, UserProfile
from datetime import datetime
import json
import logging

BOT_TOKEN = "8954981282:AAFPuBkSQCqXfMWCtUyFfDIsVp0HhlarZLw"
GROUP_ID = -4983646908

logging.basicConfig(level=logging.INFO)

def format_price(price):
    return f"{int(price):,}".replace(',', ' ')

def get_cart_items(telegram_id):
    cart, _ = Cart.objects.get_or_create(telegram_id=telegram_id)
    items = []
    total = 0
    
    for item in cart.items:
        try:
            product = Product.objects.get(id=item['id'], is_active=True)
            quantity = item.get('quantity', 1)
            subtotal = float(product.price) * quantity
            total += subtotal
            items.append({
                'id': product.id,
                'name': product.name,
                'price': float(product.price),
                'price_format': format_price(product.price),
                'quantity': quantity,
                'subtotal': subtotal,
                'subtotal_format': format_price(subtotal),
            })
        except Product.DoesNotExist:
            pass
    
    return items, total

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛍️ Каталог товаров", callback_data="products")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="show_cart")],
        [InlineKeyboardButton("📋 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    UserProfile.objects.get_or_create(
        telegram_id=user.id,
        defaults={'username': user.username or '', 'first_name': user.first_name or 'Пользователь'}
    )
    
    text = f"""
🚴‍♂️ *Добро пожаловать в Velosher Shop!*

Здравствуйте, {user.first_name}! 👋

🛍️ *Что вы можете сделать:*
• Просмотреть каталог товаров
• Добавить товары в корзину
• Оформить заказ
• Отслеживать свои заказы

Нажмите *"Каталог товаров"* чтобы начать покупки! 🚲
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    products = Product.objects.filter(is_active=True)
    if not products:
        await query.edit_message_text("😕 Товаров пока нет.")
        return
    
    text = "🛍️ *Наши велосипеды:*\n\n"
    keyboard = []
    
    for product in products:
        status = "✅ В наличии" if product.stock > 0 else "❌ Нет в наличии"
        text += f"*{product.name}*\n"
        if product.description:
            text += f"📝 {product.description[:50]}...\n"
        text += f"💰 {format_price(product.price)} сум\n{status}\n\n"
        
        if product.stock > 0:
            keyboard.append([InlineKeyboardButton(f"🛒 Добавить {product.name[:15]}", callback_data=f"add_{product.id}")])
    
    keyboard.append([
        InlineKeyboardButton("🛒 Корзина", callback_data="show_cart"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    ])
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

# ... (добавьте все остальные функции бота)

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏠 *Главное меню*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_products, pattern='^products$'))
    app.add_handler(CallbackQueryHandler(main_menu, pattern='^main_menu$'))
    # ... добавьте остальные обработчики
    
    print("🤖 Бот запущен!")
    app.run_polling()