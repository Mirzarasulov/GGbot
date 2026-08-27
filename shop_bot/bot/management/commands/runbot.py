from django.core.management.base import BaseCommand
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from bot.models import Product, Order, UserAnalytics
from django.conf import settings
import json
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Запуск Telegram бота'
    
    def handle(self, *args, **options):
        self.stdout.write('🚀 Бот запускается...')
        application = Application.builder().token(settings.BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_handler))
        application.add_handler(MessageHandler(filters.PHOTO, self.photo_handler))
        application.add_handler(MessageHandler(filters.LOCATION, self.location_handler))
        application.add_handler(MessageHandler(filters.CONTACT, self.contact_handler))
        
        application.run_polling()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        analytics, created = UserAnalytics.objects.get_or_create(
            user_id=str(user.id),
            defaults={'username': user.username, 'first_name': user.first_name}
        )
        if not created:
            analytics.username = user.username
            analytics.first_name = user.first_name
            analytics.save()
        
        keyboard = [
            [InlineKeyboardButton("🛍️ Открыть магазин", web_app=WebAppInfo(url="https://your-domain.com/"))],
            [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""
🚲 *Добро пожаловать в Velosher!* {user.first_name}

Лучшие велосипеды по выгодным ценам 🇺🇿

💰 *Цены в SUM*
🚚 *Бесплатная доставка* при заказе от 5,000,000 SUM
🛡 *Гарантия качества*

👇 Нажмите *"Открыть магазин"*, чтобы начать покупки!
"""
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "my_orders":
            user_id = str(query.from_user.id)
            orders = Order.objects.filter(user_id=user_id).order_by('-created_at')[:5]
            
            if not orders:
                await query.message.reply_text("📭 У вас пока нет заказов.")
                return
            
            text = "📦 *Ваши заказы:*\n\n"
            for order in orders:
                status_emoji = {'new': '🟡', 'paid': '🟢', 'completed': '✅', 'cancelled': '❌'}.get(order.status, '⚪️')
                text += f"{status_emoji} Заказ #{order.id} - {order.total_price} SUM\n"
                text += f"   Статус: {dict(Order.STATUS_CHOICES).get(order.status)}\n\n"
            
            await query.message.reply_text(text, parse_mode='Markdown')
        
        elif query.data == "help":
            await query.message.reply_text("""
ℹ️ *Как сделать заказ:*

1️⃣ Нажмите "Открыть магазин"
2️⃣ Выберите товары и добавьте в корзину
3️⃣ Оформите заказ
4️⃣ Оплатите картой
5️⃣ Отправьте скриншот оплаты
6️⃣ Укажите адрес доставки

📞 По вопросам: @support
""", parse_mode='Markdown')
    
    async def text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Обработка текстовых сообщений (адрес и т.д.)
        pass
    
    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        photo_file = await update.message.photo[-1].get_file()
        
        file_name = f"payment_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = os.path.join(settings.MEDIA_ROOT, 'payments', file_name)
        await photo_file.download_to_drive(file_path)
        
        order = Order.objects.filter(user_id=user_id, status='new').last()
        if order:
            order.payment_screenshot = f'payments/{file_name}'
            order.status = 'paid'
            order.save()
            
            await update.message.reply_text("✅ Оплата подтверждена! Заказ принят.")
            
            # Отправка в группу
            text = f"""
🛒 *НОВЫЙ ЗАКАЗ #{order.id}*

👤 Покупатель: @{order.username or 'без username'}
📞 Телефон: {order.phone}
📍 Адрес: {order.address}

📦 Товары:
{order.items}

💰 Сумма: {order.total_price} SUM
"""
            keyboard = [[
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{order.id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order.id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.bot.send_message(
                chat_id=settings.GROUP_CHAT_ID,
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Заказ не найден.")
    
    async def location_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        location = update.message.location
        
        order = Order.objects.filter(user_id=user_id, status='new').last()
        if order:
            order.location_lat = location.latitude
            order.location_lng = location.longitude
            order.address = f"📍 Широта: {location.latitude}, Долгота: {location.longitude}"
            order.save()
            await update.message.reply_text("✅ Адрес доставки сохранен!")
        else:
            await update.message.reply_text("❌ Заказ не найден.")
    
    async def contact_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        contact = update.message.contact
        
        order = Order.objects.filter(user_id=user_id, status='new').last()
        if order:
            order.phone = contact.phone_number
            order.save()
            await update.message.reply_text("✅ Телефон сохранен!")
        else:
            await update.message.reply_text("❌ Заказ не найден.")