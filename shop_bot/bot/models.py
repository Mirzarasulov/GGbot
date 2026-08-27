from django.db import models
from django.utils import timezone
import random

# ============================================
# МОДЕЛЬ ТОВАРА
# ============================================
class Product(models.Model):
    """Модель товара в магазине"""
    name = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    price = models.DecimalField('Цена (сум)', max_digits=15, decimal_places=0)
    old_price = models.DecimalField('Старая цена', max_digits=15, decimal_places=0, blank=True, null=True)
    stock = models.IntegerField('Количество', default=0)
    image = models.ImageField('Фото', upload_to='products/', blank=True, null=True)
    category = models.CharField('Категория', max_length=100, default='Велосипеды')
    is_active = models.BooleanField('Активен', default=True)
    is_featured = models.BooleanField('Рекомендуемый', default=False)
    views = models.IntegerField('Просмотров', default=0)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
    
    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def price_format(self):
        """Форматированная цена с пробелами"""
        return f"{int(self.price):,}".replace(',', ' ')
    
    @property
    def discount(self):
        """Процент скидки"""
        if self.old_price and self.old_price > self.price:
            return int((1 - self.price / self.old_price) * 100)
        return 0
    
    @property
    def in_stock(self):
        """Есть ли товар в наличии"""
        return self.stock > 0

# ============================================
# МОДЕЛЬ ЗАКАЗА
# ============================================
class Order(models.Model):
    """Модель заказа"""
    STATUS_CHOICES = [
        ('pending', '⏳ Ожидает оплаты'),
        ('paid', '✅ Оплачен'),
        ('shipped', '🚚 Отправлен'),
        ('delivered', '📦 Доставлен'),
        ('cancelled', '❌ Отменен'),
    ]
    
    order_id = models.CharField('Номер заказа', max_length=50, unique=True)
    telegram_id = models.BigIntegerField('Telegram ID', null=True, blank=True)
    user_name = models.CharField('Имя покупателя', max_length=200, blank=True)
    phone = models.CharField('Телефон', max_length=20)
    address = models.TextField('Адрес доставки')
    location = models.CharField('Локация', max_length=255, blank=True)
    location_lat = models.CharField('Широта', max_length=50, blank=True)
    location_lng = models.CharField('Долгота', max_length=50, blank=True)
    products = models.JSONField('Товары', default=list)
    total_amount = models.DecimalField('Сумма', max_digits=15, decimal_places=0)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_screenshot = models.ImageField('Скриншот оплаты', upload_to='payments/', blank=True, null=True)
    comment = models.TextField('Комментарий к заказу', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
    
    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Заказ #{self.order_id}"
    
    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"{timezone.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
        super().save(*args, **kwargs)
    
    @property
    def total_format(self):
        """Форматированная сумма заказа"""
        return f"{int(self.total_amount):,}".replace(',', ' ')
    
    @property
    def status_display(self):
        """Отображение статуса"""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    
    @property
    def status_emoji(self):
        """Эмодзи статуса"""
        emojis = {
            'pending': '⏳',
            'paid': '✅',
            'shipped': '🚚',
            'delivered': '📦',
            'cancelled': '❌'
        }
        return emojis.get(self.status, '❓')
    
    def get_location_link(self):
        """Ссылка на карту"""
        if self.location_lat and self.location_lng:
            return f"https://maps.google.com/maps?q={self.location_lat},{self.location_lng}"
        if self.location:
            loc = self.location.replace(' ', '')
            return f"https://maps.google.com/maps?q={loc}"
        return ""

# ============================================
# МОДЕЛЬ КОРЗИНЫ
# ============================================
class Cart(models.Model):
    """Модель корзины пользователя"""
    telegram_id = models.BigIntegerField('Telegram ID', unique=True, null=True, blank=True)
    session_key = models.CharField('Ключ сессии', max_length=100, null=True, blank=True)
    items = models.JSONField('Товары', default=list)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
    
    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'
    
    def __str__(self):
        return f"Корзина {self.telegram_id or self.session_key}"
    
    @property
    def items_count(self):
        """Количество товаров в корзине"""
        return len(self.items)
    
    @property
    def total_items(self):
        """Общее количество товаров (с учетом количества)"""
        return sum(item.get('quantity', 1) for item in self.items)
    
    @property
    def total_price(self):
        """Общая сумма корзины"""
        total = 0
        for item in self.items:
            total += item.get('price', 0) * item.get('quantity', 1)
        return total
    
    @property
    def total_format(self):
        """Форматированная общая сумма"""
        return f"{int(self.total_price):,}".replace(',', ' ')
    
    def add_item(self, product_id, quantity=1):
        """Добавить товар в корзину"""
        for item in self.items:
            if item.get('id') == product_id:
                item['quantity'] = item.get('quantity', 0) + quantity
                self.save()
                return True
        self.items.append({'id': product_id, 'quantity': quantity})
        self.save()
        return True
    
    def remove_item(self, product_id):
        """Удалить товар из корзины"""
        self.items = [item for item in self.items if item.get('id') != product_id]
        self.save()
        return True
    
    def clear(self):
        """Очистить корзину"""
        self.items = []
        self.save()
        return True

# ============================================
# МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ
# ============================================
class UserProfile(models.Model):
    """Модель профиля пользователя"""
    telegram_id = models.BigIntegerField('Telegram ID', unique=True)
    username = models.CharField('Username', max_length=100, blank=True)
    first_name = models.CharField('Имя', max_length=100)
    last_name = models.CharField('Фамилия', max_length=100, blank=True)
    phone = models.CharField('Телефон', max_length=20, blank=True)
    address = models.TextField('Адрес', blank=True)
    location = models.CharField('Локация', max_length=255, blank=True)
    location_lat = models.CharField('Широта', max_length=50, blank=True)
    location_lng = models.CharField('Долгота', max_length=50, blank=True)
    total_orders = models.IntegerField('Всего заказов', default=0)
    total_spent = models.DecimalField('Потрачено', max_digits=15, decimal_places=0, default=0)
    is_active = models.BooleanField('Активен', default=True)
    is_admin = models.BooleanField('Администратор', default=False)
    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
    last_activity = models.DateTimeField('Последняя активность', auto_now=True)
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.first_name} (@{self.username})"
    
    def get_full_name(self):
        """Полное имя пользователя"""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name
    
    def get_location_link(self):
        """Ссылка на карту"""
        if self.location_lat and self.location_lng:
            return f"https://maps.google.com/maps?q={self.location_lat},{self.location_lng}"
        if self.location:
            loc = self.location.replace(' ', '')
            return f"https://maps.google.com/maps?q={loc}"
        return ""
    
    @property
    def total_spent_format(self):
        """Форматированная сумма трат"""
        return f"{int(self.total_spent):,}".replace(',', ' ')
    
    def update_stats(self):
        """Обновить статистику пользователя"""
        orders = Order.objects.filter(telegram_id=self.telegram_id, status='paid')
        self.total_orders = orders.count()
        self.total_spent = orders.aggregate(total=models.Sum('total_amount'))['total'] or 0
        self.save()

# ============================================
# МОДЕЛЬ ОТЗЫВОВ (ДОПОЛНИТЕЛЬНО)
# ============================================
class Review(models.Model):
    """Модель отзыва о товаре"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name='Пользователь')
    rating = models.IntegerField('Оценка', choices=[(i, i) for i in range(1, 6)])
    text = models.TextField('Текст отзыва', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
    
    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Отзыв на {self.product.name} от {self.user.first_name}"

# ============================================
# МОДЕЛЬ УВЕДОМЛЕНИЙ (ДОПОЛНИТЕЛЬНО)
# ============================================
class Notification(models.Model):
    """Модель уведомлений"""
    TYPE_CHOICES = [
        ('order', 'Заказ'),
        ('payment', 'Оплата'),
        ('delivery', 'Доставка'),
        ('system', 'Системное'),
    ]
    
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name='Пользователь', null=True, blank=True)
    type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES)
    title = models.CharField('Заголовок', max_length=200)
    message = models.TextField('Сообщение')
    is_read = models.BooleanField('Прочитано', default=False)
    link = models.CharField('Ссылка', max_length=255, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_type_display()}: {self.title}"