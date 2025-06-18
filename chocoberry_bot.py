import asyncio
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from sqlalchemy.exc import IntegrityError

# Танзимоти logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Бор кардани тағйирёбандаҳои муҳит
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
if not TOKEN:
    raise ValueError("BOT_TOKEN дар муҳит муайян нашудааст!")
if not GROUP_CHAT_ID:
    raise ValueError("GROUP_CHAT_ID дар муҳит муайян нашудааст!")

INSTAGRAM_URL = os.getenv("INSTAGRAM_URL")
TIKTOK_URL = os.getenv("TIKTOK_URL")




# Танзими бот ва диспетчер
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Танзими SQLAlchemy
Base = declarative_base()
engine = create_engine("sqlite:///chocoberry.db", echo=False)
Session = sessionmaker(bind=engine)

# Моделҳо
class Category(Base):
    __tablename__ = "category"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    image_id = Column(String, nullable=True)  # Майдони нав барои тасвири категория
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "product"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    category_id = Column(Integer, ForeignKey("category.id"), nullable=True)
    category = relationship("Category", back_populates="products")
    image_id = Column(String, nullable=True)
    carts = relationship("Cart", back_populates="product")
    orders = relationship("Order", back_populates="product")

class User(Base):
    __tablename__ = "user"
    telegram_id = Column(Integer, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    language = Column(String, default="tj")
    profile = relationship("UserProfile", uselist=False, back_populates="user")
    carts = relationship("Cart", back_populates="user")
    cashback = relationship("Cashback", uselist=False, back_populates="user")
    orders = relationship("Order", back_populates="user")

class UserProfile(Base):
    __tablename__ = "userprofile"
    telegram_id = Column(Integer, ForeignKey("user.telegram_id"), primary_key=True)
    phone_number = Column(String)
    address = Column(String)
    user = relationship("User", back_populates="profile")

class Cart(Base):
    __tablename__ = "cart"
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, ForeignKey("user.telegram_id"))
    product_id = Column(Integer, ForeignKey("product.id"))
    quantity = Column(Integer, nullable=False)
    user = relationship("User", back_populates="carts")
    product = relationship("Product", back_populates="carts")

class Order(Base):
    __tablename__ = "order"
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, ForeignKey("user.telegram_id"))
    product_id = Column(Integer, ForeignKey("product.id"))
    quantity = Column(Integer, nullable=False)
    total = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")

class Cashback(Base):
    __tablename__ = "cashback"
    telegram_id = Column(Integer, ForeignKey("user.telegram_id"), primary_key=True)
    amount = Column(Float, default=0.0)
    user = relationship("User", back_populates="cashback")

# Сохтани ҷадвалҳо
Base.metadata.create_all(engine)

# Мошинҳои вазъият
class ProfileForm(StatesGroup):
    phone = State()
    address = State()

class AdminProductForm(StatesGroup):
    name = State()
    description = State()
    price = State()
    category = State()
    image = State()

class AdminOrderForm(StatesGroup):
    user = State()
    product = State()
    quantity = State()

class AdminCategoryForm(StatesGroup):
    name = State()
    image = State()  # Ҳолати нав барои тасвир
    
class OrderConfirmation(StatesGroup):
    confirm_cashback = State()
    payment_method = State()  
    
class FeedbackForm(StatesGroup):
    feedback_text = State() 
    


class UpdateProductForm(StatesGroup):
    product_id = State()    # ID-и маҳсулоти интихобшуда
    name = State()         # Номи нав
    description = State()  # Тавсифи нав
    price = State()        # Нархи нав
    category = State()     # Категорияи нав
    image = State()        # Тасвири нав       
    
    
    
# Тарҷумаҳо
TRANSLATIONS = {
    "tj": {
        "welcome": "<b>🍫🍓 Хуш омадед ба ChocoBerry!</b>\nЯк амалро интихоб кунед:",
        "choose_language": "Лутфан, забонро интихоб кунед:",
        "menu": "🍫 Меню",
        "cart": "🛒 Сабад",
        "profile": "👤 Профил",
        "cashback": "💰 Кэшбэк",
        "order_history": "📜 Таърихи фармоишҳо",
        "admin_panel": "🔧 Панели админ",
        "language_changed": "Забон ба {language} тағйир ёфт! ✅",
        "no_orders": "Шумо ягон фармоиш надоред! 😔 Лутфан, маҳсулотро ба сабад илова кунед ва фармоиш диҳед.",
        "product_added": "Маҳсулот '{name}' <b>илова шуд!</b>",
        "choose_category": "📋 Категорияро интихоб кунед:",
        "no_categories": "Ягон категория мавҷуд нест!",
        "product": "Маҳсулот",
        "quantity": "Миқдор",
        "total": "Ҳамагӣ",
        "date": "Сана",
        "product_deleted": "Маҳсулот хазф шудааст",
        "error": "Хато рух дод, лутфан дубора кӯшиш кунед! 😞",
        "invalid_image": "Лутфан, тасвир бор кунед ё /skip-ро истифода баред!",
        "product_exists": "Маҳсулот бо номи '{name}' аллакай мавҷуд аст! Лутфан, номи дигар интихоб кунед.",
        "add_another_product": "Иловаи маҳсулоти дигар",
        "back_to_admin": "Ба панели админ",
        "next_action": "Амали навбатӣ:",
        "add_to_cart_button": "📥 Илова ба сабад: {name}",
        "price": "Нарх",
        "no_access": "Шумо дастрасӣ ба ин амал надоред!",
        "manage_categories": "Идоракунии Категорияҳо",
        "cart_empty": "Сабади шумо холӣ аст! 🛒",
        "profile_missing": "Лутфан, аввал профили худро пур кунед! 📋",
        "new_order": "📦 Фармоиши нав",
        "user": "Корбар",
        "phone": "Рақами телефон",
        "products": "Маҳсулотҳо",
        "cashback_earned": "Кэшбэки бадастоварда",
        "order_confirmed": "<b>✅ Фармоиши шумо тасдиқ шуд!</b> Сабад холӣ шуд.",
        "group_notification_error": "Хато дар фиристодани огоҳӣ ба гуруҳ: {error}",
        "product_not_found": "Маҳсулот ёфт нашуд! 😔",
        "confirm_delete_product": "<b>Оё шумо мутмаинед, ки мехоҳед маҳсулоти '{name}'-ро ҳазф кунед?</b>\nИн амал сабадҳо ва фармоишҳои марбутро низ нест мекунад!",
        "yes_delete": "✅ Бале, ҳазф кун",
        "no_cancel": "❌ Не, бекор кун",
        "enter_new_phone": "Лутфан, рақами нави телефонро ворид кунед:",
        "address": "🏪 Нуқтаҳои фурӯши мо:\n\n1. Дом Печaт (маркази шаҳр)\n2. Ашан, ошёнаи 3 (фудкорт)\n3. Сиёма Мол, ошёнаи 2\n\n🕒 Соатҳои корӣ: 10:00-23:00",
        "contacts": "📱 Тамосҳои мо:\n\n☎️ Телефон барои фармоиш:\n+992 900-58-52-49\n+992 877-80-80-02\n\n💬 Ҳар вақт ба мо нависед!",
        "back_to_categories": "Бозгашт ба категорияҳо",
        "no_orders_admin": "Ягон фармоиш мавҷуд нест!",
        "order_list": "Рӯйхати фармоишҳо",
        "total_all_orders": "Маблағи умумии фармоишҳо",
        "cashback_used": "Кэшбэк дар ҳаҷми {amount:.2f} сомонӣ истифода шуд!",
        "cashback_available": "Шумо {amount:.2f} сомонӣ кэшбэк доред. Оё мехоҳед онро истифода баред?",
        "use_cashback": "Истифодаи кэшбэк",
        "skip_cashback": "Бе кэшбэк идома диҳед",
        "choose_payment_method": "Лутфан, усули пардохтро интихоб кунед:",
        "payment_cash": "💵 Нақд",
        "payment_card": "💳 Корти бонкӣ",
        "payment_method_selected": "Усули пардохт: {method} интихоб шуд.",
        "order_details_payment": "Усули пардохт: {method}",
        "feedback": "📝 Фикру мулоҳиза",
        "send_feedback": "Лутфан, фикру мулоҳизаи худро нависед:",
        "feedback_sent": "✅ Фикру мулоҳизаи шумо бо муваффақият фиристода шуд! Ташаккур барои бозгашт.",
        "feedback_empty": "Лутфан, матни фикру мулоҳизаи худро ворид кунед!",
        "feedback_notification": "📝 Фикру мулоҳизаи нав\n\n👤 Корбар: {first_name} (@{username})\n📜 Матн: {feedback_text}\n📅 Сана: {date}",
        "social_media": "🌐 Мо дар шабакаҳои иҷтимоӣ",
        "social_media_links": "📱 Бо мо дар шабакаҳои иҷтимоӣ пайваст шавед:\n\n📸 <a href='{instagram_url}'>Instagram</a>\n🎥 <a href='{tiktok_url}'>TikTok</a>",
        "address": "🏪 Суроға",
        "contacts": "📱 Контактҳо",
        "address_text": "🏪 Нуқтаҳои фурӯши мо:\n\n1. Дом Печать (маркази шаҳр)\n2. Ашан, ошёнаи 3 (фудкорт)\n3. Сиёма Мол, ошёнаи 2\n\n🕒 Соатҳои корӣ: 10:00-23:00",
        "contacts_text": "📱 Тамосҳои мо:\n\n☎️ Телефон барои фармоиш:\n+992 900-58-52-49\n+992 877-80-80-02\n\n💬 Ҳар вақт ба мо нависед!",
        "admin_update_product": "📝 Навсозии Маҳсулот",
        "select_product_to_update": "Маҳсулотеро барои навсозӣ интихоб кунед:",
        "no_products": "Маҳсулот мавҷуд нест!",
        "update_product_name": "Номи нави маҳсулотро ворид кунед:",
        "update_product_description": "Тавсифи нави маҳсулотро ворид кунед (ихтиёрӣ, барои гузаштан '⏭ Гузаштан' нависед):",
        "update_product_price": "Нархи нави маҳсулотро ворид кунед (бо сомонӣ):",
        "update_product_category": "Категорияи нави маҳсулотро интихоб кунед:",
        "update_product_image": "Тасвири нави маҳсулотро бор кунед (ихтиёрӣ, барои гузаштан '⏭ Гузаштан' нависед):",
        "product_updated": "✅ Маҳсулот бомуваффақият навсозӣ шуд!",
        "invalid_price": "Нархи нодуруст! Лутфан, рақами мусбат ворид кунед.",
        "skip": "⏭ Гузаштан",
        "no_access": "🚫 Шумо дастрасӣ ба панели админ надоред!",
        "invalid_phone": "Рақами нодуруст! {error}",
        "enter_address": "Лутфан, суроғаро ворид кунед:",
        "add_product" : "➕ Иловаи Маҳсулот",
        "delete_product": "🗑 Ҳазфи Маҳсулот",
        "add_order": "📦 Иловаи Фармоиш",
        "view_orders": "📜 Рӯйхати Фармоишҳо",
        "select_action": "Амали дилхоҳро интихоб кунед",
        "back_to_main": "🔙 Ба Менюи Асосӣ",
        "select_category_to_edit": "Категорияро барои таҳрир интихоб кунед:",
        "back_to_manage_categories": "🔙 Бозгашт ба идоракунии категорияҳо",    
        "contact_info": "📍 Маълумот барои тамос",
        "choose_contact_info": "Лутфан, интихоб кунед: суроға ё контактҳо",
        "welcome_intro": "📋 Бо мо шумо метавонед:\n- Маҳсулотро аз меню интихоб кунед\n- Фармоиш диҳед ва кэшбэк ба даст оред\n- Профили худро идора кунед\n- Бо мо дар тамос шавед" ,
        "cashback_info": "📌 Агар кэшбэк истифода кунед, маблағи фармоиш ({total:.2f} сомон) кам мешавад.",
        "address_text": "🏪 Нуқтаҳои фурӯши мо:\n\n1. Дом Печать (маркази шаҳр)\n2. Ашан, ошёнаи 3 (фудкорт)\n3. Сиёма Мол, ошёнаи 2\n\n🕒 Соатҳои корӣ: 10:00-23:00",
        "contacts_text": "📱 Тамосҳои мо:\n\n☎️ Телефон барои фармоиш:\n+992 900-58-52-49\n+992 877-80-80-02\n\n💬 Ҳар вақт ба мо нависед!",
        "choose_contact_info": "Лутфан, интихоб кунед: суроға ё контактҳо",
        "whatsapp_1": "📱 WhatsApp (+992900585249)",
        "whatsapp_2": "📱 WhatsApp (+992877808002)",
    },
    "ru": {
        "welcome": "<b>🍫🍓 Добро пожаловать в ChocoBerry!</b>\nВыберите действие:",
        "choose_language": "Пожалуйста, выберите язык:",
        "menu": "🍫 Меню",
        "cart": "🛒 Корзина",
        "profile": "👤 Профиль",
        "cashback": "💰 Кэшбэк",
        "order_history": "📜 История заказов",
        "admin_panel": "🔧 Панель администратора",
        "language_changed": "Язык изменён на {language}! ✅",
        "no_orders": "У вас нет заказов! 😔 Пожалуйста, добавьте товары в корзину и оформите заказ.",
        "product_added": "Товар '{name}' <b>добавлен!</b>",
        "choose_category": "📋 Выберите категорию:",
        "no_categories": "Нет доступных категорий!",
        "product": "Товар",
        "quantity": "Количество",
        "total": "Итого",
        "date": "Дата",
        "product_deleted": "Товар удалён",
        "error": "Произошла ошибка, попробуйте снова! 😞",
        "invalid_image": "Пожалуйста, загрузите изображение или используйте /skip!",
        "product_exists": "Товар с названием '{name}' уже существует! Выберите другое название.",
        "add_another_product": "Добавить другой товар",
        "back_to_admin": "В панель администратора",
        "next_action": "Следующее действие:",
        "add_to_cart_button": "📥 Добавить в корзину: {name}",
        "price": "Цена",
        "no_access": "У вас нет доступа к этому действию!",
        "manage_categories": "Управление категориями",
        "cart_empty": "Ваша корзина пуста! 🛒",
        "profile_missing": "Пожалуйста, сначала заполните свой профиль! 📋",
        "new_order": "📦 Новый заказ",
        "user": "Пользователь",
        "phone": "Номер телефона",
        "products": "Товары",
        "cashback_earned": "Заработанный кэшбэк",
        "order_confirmed": "<b>✅ Ваш заказ подтверждён!</b> Корзина очищена.",
        "group_notification_error": "Ошибка при отправке уведомления в группу: {error}",
        "product_not_found": "Товар не найден! 😔",
        "confirm_delete_product": "<b>Вы уверены, что хотите удалить товар '{name}'?</b>\nЭто действие также удалит связанные корзины и заказы!",
        "yes_delete": "✅ Да, удалить",
        "no_cancel": "❌ Нет, отменить",
        "enter_new_phone": "Пожалуйста, введите новый номер телефона:",
        "address": "🏪 Наши пункты продаж:\n\n1. Дом печати (центр города)\n2. Ашан, 3 этаж (фудкорт)\n3. Сиёма Мол, 2 этаж\n\n🕒 График работы: 10:00-23:00",
        "contacts": "📱 Наши контакты:\n\n☎️ Телефон для заказов:\n+992 900-58-52-49\n+992 877-80-80-02\n\n💬 Пишите нам в любое время!",
        "back_to_categories": "Вернуться к категориям",
        "no_orders_admin": "Нет заказов!",
        "order_list": "Список заказов",
        "total_all_orders": "Общая сумма заказов",
        "cashback_used": "Кэшбэк в размере {amount:.2f} сомони использован!",
        "cashback_available": "У вас есть {amount:.2f} сомони кэшбэка. Хотите использовать?",
        "use_cashback": "Использовать кэшбэк",
        "skip_cashback": "Продолжить без кэшбэка",
        "choose_payment_method": "Пожалуйста, выберите способ оплаты:",
        "payment_cash": "💵 Наличные",
        "payment_card": "💳 Банковская карта",
        "payment_method_selected": "Способ оплаты: {method} выбран.",
        "order_details_payment": "Способ оплаты: {method}",
        "feedback": "📝 Отзыв",
        "send_feedback": "Пожалуйста, напишите ваш отзыв:",
        "feedback_sent": "✅ Ваш отзыв успешно отправлен! Спасибо за обратную связь.",
        "feedback_empty": "Пожалуйста, введите текст отзыва!",
        "feedback_notification": "📝 Новый отзыв\n\n👤 Пользователь: {first_name} (@{username})\n📜 Текст: {feedback_text}\n📅 Дата: {date}",
        "social_media": "🌐 Мы в социальных сетях",
        "social_media_links": "📱 Присоединяйтесь к нам в социальных сетях:\n\n📸 <a href='{instagram_url}'>Instagram</a>\n🎥 <a href='{tiktok_url}'>TikTok</a>",
        "address": "🏪 Адрес",
        "contacts": "📱 Контакты",
        "address_text": "🏪 Наши пункты продаж:\n\n1. Дом печати (центр города)\n2. Ашан, 3 этаж (фудкорт)\n3. Сиёма Мол, 2 этаж\n\n🕒 График работы: 10:00-23:00",
        "contacts_text": "📱 Наши контакты:\n\n☎️ Телефон для заказов:\n+992 900-58-52-49\n+992 877-80-80-02\n\n💬 Пишите нам в любое время!",
        "admin_update_product": "📝 Обновление Продукта",
        "select_product_to_update": "Выберите продукт для обновления:",
        "no_products": "Продукты отсутствуют!",
        "update_product_name": "Введите новое название продукта:",
        "update_product_description": "Введите новое описание продукта (необязательно, для пропуска напишите '⏭ Пропустить'):",
        "update_product_price": "Введите новую цену продукта (в сомони):",
        "update_product_category": "Выберите новую категорию продукта:",
        "update_product_image": "Загрузите новое изображение продукта (необязательно, для пропуска напишите '⏭ Пропустить'):",
        "product_updated": "✅ Продукт успешно обновлен!",
        "invalid_price": "Неверная цена! Пожалуйста, введите положительное число.",
        "skip": "⏭ Пропустить",
        "no_access": "🚫 У вас нет доступа к панели админа!",   
        "invalid_phone": "Неверный номер! {error}",
        "enter_address": "Пожалуйста, введите адрес:",
        "add_product": "➕ Добавить Продукт",
        "delete_product": "🗑 Удалить Продукт",
        "add_order": "📦 Добавить Заказ",
        "view_orders": "📜 Список Заказов",
        "select_action": "Выберите желаемое действие",
        "back_to_main": "🔙 В Главное Меню",
        "select_category_to_edit": "Выберите категорию для редактирования:",
        "back_to_manage_categories": "🔙 Вернуться к управлению категориями",
        "contact_info": "📍 Контактная информация",
        "choose_contact_info": "Пожалуйста, выберите: адрес или контакты",
        "welcome_intro": "📋 С нами вы можете:\n- Выбирать товары из меню\n- Оформлять заказы и получать кэшбэк\n- Управлять профилем\n- Связаться с нами",
        "cashback_info": "📌 Если вы используете кэшбэк, сумма заказа ({total:.2f} сомони) уменьшится.",
        "whatsapp_1": "📱 WhatsApp (+992900585249)",
        "whatsapp_2": "📱 WhatsApp (+992877808002)",
    },
    "en": {
        "welcome": "<b>🍫🍓 Welcome to ChocoBerry!</b>\nChoose an action:",
        "choose_language": "Please select a language:",
        "menu": "🍫 Menu",
        "cart": "🛒 Cart",
        "profile": "👤 Profile",
        "cashback": "💰 Cashback",
        "order_history": "📜 Order History",
        "admin_panel": "🔧 Admin Panel",
        "language_changed": "Language changed to {language}! ✅",
        "no_orders": "You have no orders! 😔 Please add products to your cart and place an order.",
        "product_added": "Product '{name}' <b>added!</b>",
        "choose_category": "📋 Select a category:",
        "no_categories": "No categories available!",
        "product": "Product",
        "quantity": "Quantity",
        "total": "Total",
        "date": "Date",
        "product_deleted": "Product deleted",
        "error": "An error occurred, please try again! 😞",
        "invalid_image": "Please upload an image or use /skip!",
        "product_exists": "Product with name '{name}' already exists! Please choose another name.",
        "add_another_product": "Add another product",
        "back_to_admin": "Back to admin panel",
        "next_action": "Next action:",
        "add_to_cart_button": "📥 Add to Cart: {name}",
        "price": "Price",
        "no_access": "You don't have access to this action!",
        "manage_categories": "Category Management",
        "cart_empty": "Your cart is empty! 🛒",
        "profile_missing": "Please fill out your profile first! 📋",
        "new_order": "📦 New Order",
        "user": "User",
        "phone": "Phone Number",
        "products": "Products",
        "cashback_earned": "Earned Cashback",
        "order_confirmed": "<b>✅ Your order has been confirmed!</b> Cart cleared.",
        "group_notification_error": "Error sending notification to group: {error}",
        "product_not_found": "Product not found! 😔",
        "confirm_delete_product": "<b>Are you sure you want to delete the product '{name}'?</b>\nThis will also remove related carts and orders!",
        "yes_delete": "✅ Yes, delete",
        "no_cancel": "❌ No, cancel",
        "enter_new_phone": "Please enter a new phone number:",
        "address": "🏪 Our sales points:\n\n1. Dom Pechati (city center)\n2. Auchan, 3rd floor (food court)\n3. Siyoma Mall, 2nd floor\n\n🕒 Working hours: 10:00-23:00",
        "contacts": "📱 Our contacts:\n\n☎️ Phone for orders:\n+992 900-58-52-49\n+992 877-80-80-02\n\n💬 Write to us anytime!",
        "back_to_categories": "Back to categories",
        "no_orders_admin": "No orders available!",
        "order_list": "Order List",
        "total_all_orders": "Total amount of orders",
        "cashback_used": "Cashback of {amount:.2f} somoni has been used!",
        "cashback_available": "You have {amount:.2f} somoni cashback. Would you like to use it?",
        "use_cashback": "Use cashback",
        "skip_cashback": "Continue without cashback",
        "choose_payment_method": "Please select a payment method:",
        "payment_cash": "💵 Cash",
        "payment_card": "💳 Bank Card",
        "payment_method_selected": "Payment method: {method} selected.",
        "order_details_payment": "Payment method: {method}",
        "feedback": "📝 Feedback",
        "send_feedback": "Please write your feedback:",
        "feedback_sent": "✅ Your feedback has been successfully sent! Thank you for your response.",
        "feedback_empty": "Please enter the text of your feedback!",
        "feedback_notification": "📝 New Feedback\n\n👤 User: {first_name} (@{username})\n📜 Text: {feedback_text}\n📅 Date: {date}",
        "social_media": "🌐 We are on Social Media",
        "social_media_links": "📱 Follow us on social media:\n\n📸 <a href='{instagram_url}'>Instagram</a>\n🎥 <a href='{tiktok_url}'>TikTok</a>",
        "address": "🏪 Address",
        "contacts": "📱 Contacts",
        "address_text": "🏪 Our sales points:\n\n1. Dom Pechati (city center)\n2. Auchan, 3rd floor (food court)\n3. Siyoma Mall, 2nd floor\n\n🕒 Working hours: 10:00-23:00",
        "contacts_text": "📱 Our contacts:\n\n☎️ Phone for orders:\n+992 900-58-52-49\n+992 877-80-80-02\n\n💬 Write to us anytime!",
        "admin_update_product": "📝 Update Product",
        "select_product_to_update": "Select a product to update:",
        "no_products": "No products available!",
        "update_product_name": "Enter the new product name:",
        "update_product_description": "Enter the new product description (optional, type '⏭ Skip' to skip):",
        "update_product_price": "Enter the new product price (in somoni):",
        "update_product_category": "Select the new product category:",
        "update_product_image": "Upload a new product image (optional, type '⏭ Skip' to skip):",
        "product_updated": "✅ Product successfully updated!",
        "invalid_price": "Invalid price! Please enter a positive number.",
        "skip": "⏭ Skip",
        "no_access": "🚫 You do not have access to the admin panel!",
        "invalid_phone": "Invalid number! {error}",
        "enter_address": "Please enter your address:",
        "add_product": "➕ Add Product",
        "delete_product": "🗑 Delete Product",
        "add_order": "📦 Add Order",
        "view_orders": "📜 View Orders",
        "select_action": "Select the desired action",
        "back_to_main": "🔙 Back to Main Menu",
        "select_category_to_edit": "Select a category to edit:",
        "back_to_manage_categories": "🔙 Back to category management",
        "contact_info": "📍 Contact Information",
        "choose_contact_info": "Please select: address or contacts"  ,  
        "welcome_intro": "📋 With us, you can:\n- Choose products from the menu\n- Place orders and earn cashback\n- Manage your profile\n- Contact us" ,
        "cashback_info": "📌 If you use cashback, the order total ({total:.2f} somoni) will be reduced." ,
        "whatsapp_1": "📱 WhatsApp (+992900585249)",
        "whatsapp_2": "📱 WhatsApp (+992877808002)",    
 
    }
}

def get_text(user_id: int, key: str, **kwargs) -> str:
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        language = user.language if user and user.language in TRANSLATIONS else "tj"
        text = TRANSLATIONS.get(language, TRANSLATIONS["tj"]).get(key, key)
        return text.format(**kwargs)
    except KeyError:
        logger.error(f"Error formatting text for key '{key}' in language '{language}'")
        return text
    finally:
        session.close()


def escape_html(text: str) -> str:
    if text is None:
        return ""
    return text.replace('&', '&').replace('<', '<').replace('>', '>')
    
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@dp.message(Command("start"))
async def start_command(message: types.Message):
    try:
        session = Session()
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name or None,
                language="tj"
            )
            session.add(user)
            session.add(Cashback(telegram_id=message.from_user.id, amount=0.0))
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Хато ҳангоми сабти корбар: {str(e)}")
                await message.answer(get_text(message.from_user.id, "error"))
                session.close()
                return

        welcome_text = (
            f"{get_text(message.from_user.id, 'welcome')}\n\n"
            f"📋 Бо мо шумо метавонед:\n"
            f"- Маҳсулотро аз меню интихоб кунед\n"
            "- Фармоиш диҳед ва кэшбэк ба даст оред\n"
            "- Профили худро идора кунед\n"
            "- Бо мо дар тамос шавед\n\n"
            f"Аввал забонро интихоб кунед:"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🇹🇯 Тоҷикӣ", callback_data="set_language_tj"),
                    InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_language_ru"),
                    InlineKeyboardButton(text="🇬🇧 English", callback_data="set_language_en")
                ]
            ]
        )
        await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
        session.close()
    except Exception as e:
        logger.error(f"Хато дар start_command: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        if 'session' in locals():
            session.close()
            

def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text=get_text(user_id, "menu")),
            KeyboardButton(text=get_text(user_id, "cart"))
        ],
        [
            KeyboardButton(text=get_text(user_id, "profile")),
            KeyboardButton(text=get_text(user_id, "cashback"))
        ],
        [
            KeyboardButton(text=get_text(user_id, "order_history")),
            KeyboardButton(text=get_text(user_id, "contact_info"))  
        ],
        [
            KeyboardButton(text=get_text(user_id, "feedback")),
            KeyboardButton(text=get_text(user_id, "social_media"))
        ]
    ]
    if is_admin(user_id):
        buttons.append([KeyboardButton(text=get_text(user_id, "admin_panel"))])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
            

@dp.callback_query(lambda c: c.data.startswith("set_language_"))
async def set_language(callback: types.CallbackQuery, state: FSMContext):
    try:
        language = callback.data.split("_")[-1]
        if language not in ["tj", "ru", "en"]:
            await callback.message.answer("Неизвестный язык!")
            await callback.answer()
            return

        session = Session()
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        profile = session.query(UserProfile).filter_by(telegram_id=callback.from_user.id).first()
        
        if user:
            user.language = language
            session.commit()
        
        session.close()

        # Check if profile exists
        if not profile:
            await callback.message.answer(get_text(callback.from_user.id, "profile_missing"))
            await callback.message.answer(get_text(callback.from_user.id, "enter_new_phone"))
            await state.set_state(ProfileForm.phone)
        else:
            keyboard = get_main_keyboard(callback.from_user.id)
            await callback.message.answer(
                get_text(callback.from_user.id, "language_changed", language=language.upper()),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в set_language: {str(e)}")
        await callback.message.answer("Произошла ошибка, пожалуйста попробуйте снова!")
        await callback.answer()
    

    
@dp.message(Command("language"))
async def change_language_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇹🇯 Тоҷикӣ", callback_data="set_language_tj"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_language_ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="set_language_en")
            ]
        ]
    )
    await message.answer(get_text(message.from_user.id, "choose_language"), reply_markup=keyboard)
    
    
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    try:
        # Истифода аз get_main_keyboard барои гирифтани клавиатураи асосӣ бо тарҷумаҳои дуруст
        keyboard = get_main_keyboard(callback.from_user.id)
        await callback.message.answer(
            text="✅ Ба менюи асосӣ баргаштед:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар back_to_main: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")
        

@dp.message(lambda message: message.text == get_text(message.from_user.id, "social_media"))
async def social_media_links(message: types.Message):
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📸 Instagram", url=INSTAGRAM_URL)],
            [InlineKeyboardButton(text="🎥 TikTok", url=TIKTOK_URL)]
        ])
        await message.answer(
            get_text(
                message.from_user.id,
                "social_media_links",
                instagram_url=INSTAGRAM_URL,
                tiktok_url=TIKTOK_URL
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Хато дар social_media_links: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        


@dp.message(lambda message: message.text in [TRANSLATIONS["tj"]["menu"], TRANSLATIONS["ru"]["menu"], TRANSLATIONS["en"]["menu"]])
async def show_menu(message: types.Message):
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await message.answer(get_text(message.from_user.id, "no_categories"))
            return

        for category in categories:
            session = Session()
            products = session.query(Product).filter_by(category_id=category.id).all()
            session.close()

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{escape_html(product.name)} - {product.price} сомонӣ",
                    callback_data=f"view_product_{product.id}"
                )] for product in products
            ])

            caption = f"<b>{escape_html(category.name)}</b>\n\n"
            if not products:
                caption += "Дар ин категория ягон маҳсулот мавҷуд нест 😔"
            else:
                caption += "Маҳсулотро аз рӯйхати зер интихоб кунед:"

            if category.image_id:
                try:
                    await message.answer_photo(
                        photo=category.image_id,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Хато дар фиристодани тасвир барои категория {category.name}: {str(e)}")
                    await message.answer(caption, reply_markup=keyboard, parse_mode="HTML")
            else:
                await message.answer(caption, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Хато дар show_menu: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        if 'session' in locals():
            session.close()
            
            
@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await callback.message.answer(get_text(callback.from_user.id, "no_categories"))
            await callback.answer()
            return

        for category in categories:
            session = Session()
            products = session.query(Product).filter_by(category_id=category.id).all()
            session.close()

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{escape_html(product.name)} - {product.price} сомонӣ",
                    callback_data=f"view_product_{product.id}"
                )] for product in products
            ])

            caption = f"<b>{escape_html(category.name)}</b>\n\n"
            if not products:
                caption += "Дар ин категория ягон маҳсулот мавҷуд нест 😔"
            else:
                caption += "Маҳсулотро аз рӯйхати зер интихоб кунед:"

            if category.image_id:
                try:
                    await callback.message.answer_photo(
                        photo=category.image_id,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Хато дар фиристодани тасвир барои категория {category.name}: {str(e)}")
                    await callback.message.answer(caption, reply_markup=keyboard, parse_mode="HTML")
            else:
                await callback.message.answer(caption, reply_markup=keyboard, parse_mode="HTML")

        await callback.answer()

    except Exception as e:
        logger.error(f"Хато дар back_to_menu: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()             
            
            
@dp.callback_query(lambda c: c.data == "admin_edit_category")
async def admin_edit_category(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await callback.message.answer(get_text(callback.from_user.id, "no_categories"))
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=category.name, callback_data=f"edit_category_{category.id}")]
                for category in categories
            ]
        )
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=get_text(callback.from_user.id, "back_to_manage_categories"), callback_data="admin_manage_categories")])

        await callback.message.answer(get_text(callback.from_user.id, "select_category_to_edit"), reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_edit_category: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("edit_category_"))
async def select_category_to_edit(callback: types.CallbackQuery, state: FSMContext):
    try:
        category_id = int(callback.data.split("_")[-1])
        await state.update_data(category_id=category_id)
        await callback.message.answer("Тасвири нав барои категория бор кунед (ё /skip барои гузаштан):")
        await state.set_state(AdminCategoryForm.image)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар select_category_to_edit: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        
                    

@dp.callback_query(lambda c: c.data.startswith("category_"))
async def show_category_products(callback: types.CallbackQuery):
    try:
        category_id = int(callback.data.split("_")[-1])
        session = Session()
        category = session.query(Category).filter_by(id=category_id).first()
        products = session.query(Product).filter_by(category_id=category_id).all()
        session.close()

        if not category:
            await callback.message.answer(get_text(callback.from_user.id, "no_categories"))
            await callback.answer()
            return

        response = f"🍫🍓 <b>{escape_html(category.name)}</b>\n\n"
        for product in products:
            caption = (
                f"<b>{escape_html(product.name)}</b>\n"
                f"{escape_html(product.description or '')}\n"
                f"💵 {get_text(callback.from_user.id, 'price')}: ${product.price}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=get_text(callback.from_user.id, "add_to_cart_button", name=escape_html(product.name)),
                    callback_data=f"add_to_cart_{product.id}"
                )]
            ])

            if product.image_id:
                try:
                    await callback.message.answer_photo(
                        photo=product.image_id,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error sending image for product {product.name}: {str(e)}")
                    await callback.message.answer(
                        caption,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
            else:
                await callback.message.answer(
                    caption,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(callback.from_user.id, "back_to_categories"), callback_data="back_to_categories")]
        ])
        await callback.message.answer(response, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in show_category_products: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data == "back_to_categories")
async def back_to_categories(callback: types.CallbackQuery):
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await callback.message.answer(get_text(callback.from_user.id, "no_categories"))
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}")]
            for category in categories
        ])
        await callback.message.answer(get_text(callback.from_user.id, "choose_category"), reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар back_to_categories: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_to_cart_"))
async def add_to_cart(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data.split("_")[-1])
        session = Session()
        existing_cart_item = session.query(Cart).filter_by(telegram_id=callback.from_user.id, product_id=product_id).first()
        if existing_cart_item:
            existing_cart_item.quantity += 1
        else:
            cart_item = Cart(telegram_id=callback.from_user.id, product_id=product_id, quantity=1)
            session.add(cart_item)
        session.commit()
        product = session.query(Product).filter_by(id=product_id).first()
        session.close()
        await callback.message.answer(
            get_text(callback.from_user.id, "product_added", name=escape_html(product.name)),
            parse_mode="HTML"  # Илова кардани parse_mode
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар add_to_cart: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.message(lambda message: message.text == get_text(message.from_user.id, "cart"))
async def view_cart(message: types.Message):
    try:
        session = Session()
        cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == message.from_user.id).all()
        profile = session.query(UserProfile).filter_by(telegram_id=message.from_user.id).first()
        cashback = session.query(Cashback).filter_by(telegram_id=message.from_user.id).first()
        session.close()

        if not cart_items:
            await message.answer(get_text(message.from_user.id, "cart_empty"))
            return

        if not profile:
            await message.answer(get_text(message.from_user.id, "profile_missing"))
            return

        total = 0
        response = "<b>🛒 Сабади шумо:</b>\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for cart_item, product in cart_items:
            item_total = product.price * cart_item.quantity
            total += item_total
            response += (
                f"📦 <b>{escape_html(product.name)}</b>\n"
                f"🔢 Миқдор: x{cart_item.quantity}\n"
                f"💵 Нарх: {item_total:.2f} сомонӣ\n\n"
            )
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="➕", callback_data=f"increase_quantity_{cart_item.id}"),
                InlineKeyboardButton(text="➖", callback_data=f"decrease_quantity_{cart_item.id}"),
                InlineKeyboardButton(text="🗑 Хориҷ", callback_data=f"remove_from_cart_{cart_item.id}")
            ])
            if product.image_id:
                await message.answer_photo(
                    photo=product.image_id,
                    caption=f"{escape_html(product.name)} - {item_total:.2f} сомонӣ",
                    parse_mode="HTML"
                )

        response += f"<b>Ҳамагӣ:</b> {total:.2f} сомонӣ\n"
        response += f"<b>Кэшбэки дастрас:</b> {cashback.amount if cashback else 0.0} сомонӣ\n"
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Тасдиқи фармоиш", callback_data="confirm_order")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Истифодаи кэшбэк", callback_data="use_cashback")])

        await message.answer(response, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Хато дар view_cart: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        

@dp.callback_query(lambda c: c.data.startswith("increase_quantity_"))
async def increase_quantity(callback: types.CallbackQuery):
    try:
        cart_item_id = int(callback.data.split("_")[-1])
        session = Session()
        cart_item = session.query(Cart).filter_by(id=cart_item_id).first()
        if cart_item:
            cart_item.quantity += 1
            session.commit()
            
            # Навсозии паёми сабад
            cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == callback.from_user.id).all()
            profile = session.query(UserProfile).filter_by(telegram_id=callback.from_user.id).first()
            cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()

            total = 0
            response = "<b>🛒 Сабади шумо:</b>\n\n"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for item, product in cart_items:
                item_total = product.price * item.quantity
                total += item_total
                response += f"{escape_html(product.name)} x{item.quantity} - {item_total} сомонӣ\n"
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(text="➕", callback_data=f"increase_quantity_{item.id}"),
                    InlineKeyboardButton(text="➖", callback_data=f"decrease_quantity_{item.id}"),
                    InlineKeyboardButton(text="🗑 Хориҷ", callback_data=f"remove_from_cart_{item.id}")
                ])

            response += f"<b>Ҳамагӣ:</b> {total} сомонӣ\n"
            response += f"<b>Кэшбэки дастрас:</b> {cashback.amount if cashback else 0.0} сомонӣ\n"
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Тасдиқи фармоиш", callback_data="confirm_order")])
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Истифодаи кэшбэк", callback_data="use_cashback")])

            await bot.edit_message_text(
                text=response,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(get_text(callback.from_user.id, "error"))
        session.close()
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар increase_quantity: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data.startswith("decrease_quantity_"))
async def decrease_quantity(callback: types.CallbackQuery):
    try:
        cart_item_id = int(callback.data.split("_")[-1])
        session = Session()
        cart_item = session.query(Cart).filter_by(id=cart_item_id).first()
        if cart_item:
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                session.commit()
            else:
                session.delete(cart_item)
                session.commit()

            # Навсозии паёми сабад
            cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == callback.from_user.id).all()
            profile = session.query(UserProfile).filter_by(telegram_id=callback.from_user.id).first()
            cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()

            if not cart_items:
                await bot.edit_message_text(
                    text=get_text(callback.from_user.id, "cart_empty"),
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    parse_mode="HTML"
                )
                session.close()
                await callback.answer()
                return

            total = 0
            response = "<b>🛒 Сабади шумо:</b>\n\n"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for item, product in cart_items:
                item_total = product.price * item.quantity
                total += item_total
                response += f"{escape_html(product.name)} x{item.quantity} - {item_total} сомонӣ\n"
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(text="➕", callback_data=f"increase_quantity_{item.id}"),
                    InlineKeyboardButton(text="➖", callback_data=f"decrease_quantity_{item.id}"),
                    InlineKeyboardButton(text="🗑 Хориҷ", callback_data=f"remove_from_cart_{item.id}")
                ])

            response += f"<b>Ҳамагӣ:</b> {total} сомонӣ\n"
            response += f"<b>Кэшбэки дастрас:</b> {cashback.amount if cashback else 0.0} сомонӣ\n"
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Тасдиқи фармоиш", callback_data="confirm_order")])
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Истифодаи кэшбэк", callback_data="use_cashback")])

            await bot.edit_message_text(
                text=response,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(get_text(callback.from_user.id, "error"))
        session.close()
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар decrease_quantity: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data.startswith("remove_from_cart_"))
async def remove_from_cart(callback: types.CallbackQuery):
    try:
        cart_item_id = int(callback.data.split("_")[-1])
        session = Session()
        cart_item = session.query(Cart).filter_by(id=cart_item_id).first()
        if cart_item:
            session.delete(cart_item)
            session.commit()

            # Навсозии паёми сабад
            cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == callback.from_user.id).all()
            profile = session.query(UserProfile).filter_by(telegram_id=callback.from_user.id).first()
            cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()

            if not cart_items:
                await bot.edit_message_text(
                    text=get_text(callback.from_user.id, "cart_empty"),
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    parse_mode="HTML"
                )
                session.close()
                await callback.answer()
                return

            total = 0
            response = "<b>🛒 Сабади шумо:</b>\n\n"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for item, product in cart_items:
                item_total = product.price * item.quantity
                total += item_total
                response += f"{escape_html(product.name)} x{item.quantity} - {item_total} сомонӣ\n"
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(text="➕", callback_data=f"increase_quantity_{item.id}"),
                    InlineKeyboardButton(text="➖", callback_data=f"decrease_quantity_{item.id}"),
                    InlineKeyboardButton(text="🗑 Хориҷ", callback_data=f"remove_from_cart_{item.id}")
                ])

            response += f"<b>Ҳамагӣ:</b> {total} сомонӣ\n"
            response += f"<b>Кэшбэки дастрас:</b> {cashback.amount if cashback else 0.0} сомонӣ\n"
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Тасдиқи фармоиш", callback_data="confirm_order")])
            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Истифодаи кэшбэк", callback_data="use_cashback")])

            await bot.edit_message_text(
                text=response,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(get_text(callback.from_user.id, "error"))
        session.close()
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар remove_from_cart: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.message(lambda message: message.text == get_text(message.from_user.id, "order_history"))
async def view_order_history(message: types.Message):
    try:
        session = Session()
        orders = session.query(Order, Product).join(Product, Order.product_id == Product.id, isouter=True).filter(Order.telegram_id == message.from_user.id).all()
        session.close()

        if not orders:
            await message.answer(get_text(message.from_user.id, "no_orders"), parse_mode="HTML")
            return

        response = f"<b>{get_text(message.from_user.id, 'order_history')}</b>\n\n"
        for order, product in orders:
            product_name = escape_html(product.name) if product else get_text(message.from_user.id, "product_deleted")
            response += f"Фармоиш #{order.id}\n"
            response += f"{get_text(message.from_user.id, 'product')}: {product_name}\n"
            response += f"{get_text(message.from_user.id, 'quantity')}: {order.quantity}\n"
            response += f"{get_text(message.from_user.id, 'total')}: {order.total} сомонӣ\n"
            response += f"{get_text(message.from_user.id, 'date')}: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        try:
            await message.answer(response, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Хатои таҳлили HTML дар view_order_history: {str(e)}")
            await message.answer(response)
    except Exception as e:
        logger.error(f"Хато дар view_order_history: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"), parse_mode="HTML")
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    try:
        session = Session()
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        if not user:
            user = User(
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name or None
            )
            session.add(user)
            session.add(Cashback(telegram_id=callback.from_user.id, amount=0.0))
            session.commit()

        cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == callback.from_user.id).all()
        profile = session.query(UserProfile).filter_by(telegram_id=callback.from_user.id).first()
        if not cart_items:
            session.close()
            await callback.message.answer(get_text(callback.from_user.id, "cart_empty"), parse_mode="HTML")
            await callback.answer()
            return
        if not profile:
            session.close()
            await callback.message_answer(get_text(callback.from_user.id, "profile_missing"))
            await callback.answer()
            return

        total = sum(product.price * cart_item.quantity for cart_item, product in cart_items)

        cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
        if not cashback:
            cashback = Cashback(telegram_id=callback.from_user.id, amount=0.0)
            session.add(cashback)
            session.commit()

        await state.update_data(total=total, cart_items=[(cart_item.id, product.id, cart_item.quantity) for cart_item, product in cart_items])

        if cashback.amount > 0:
            cashback_text = (
                f"{get_text(callback.from_user.id, 'cashback_available', amount=cashback.amount)}\n"
                f"📌 Агар кэшбэк истифода кунед, маблағи фармоиш ({total:.2f} сомон) кам мешавад.\n"
                f"Интихоб кунед:"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "use_cashback"), callback_data="apply_cashback")],
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "skip_cashback"), callback_data="skip_cashback")]]
            )
            await callback.message.answer(cashback_text, reply_markup=keyboard, parse_mode="HTML")
            await state.set_state(OrderConfirmation.confirm_cashback)
        else:
            payment_text = (
                f"<b>Фармоиши шумо: {total:.2f} сомон</b>\n"
                f"{get_text(callback.from_user.id, 'choose_payment_method')}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "payment_cash"), callback_data="payment_cash")],
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "payment_card"), callback_data="payment_card")]
            ])
            await callback.message.answer(payment_text, reply_markup=keyboard, parse_mode="HTML")
            await state.set_state(OrderConfirmation.payment_method)

        session.close()
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар confirm_order: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")
        await callback.answer()
        if 'session' in locals():
            session.close()
            


@dp.callback_query(lambda c: c.data in ["apply_cashback", "skip_cashback"])
async def handle_cashback_choice(callback: types.CallbackQuery, state: FSMContext):
    try:
        session = Session()
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        profile = session.query(UserProfile).filter_by(telegram_id=callback.from_user.id).first()
        data = await state.get_data()
        total = data.get("total", 0.0)
        cart_items_data = data.get("cart_items", [])

        cart_items = []
        for cart_id, product_id, quantity in cart_items_data:
            cart_item = session.query(Cart).filter_by(id=cart_id).first()
            product = session.query(Product).filter_by(id=product_id).first()
            if cart_item and product:
                cart_items.append((cart_item, product))

        cashback_applied = 0.0
        if callback.data == "apply_cashback":
            cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
            if cashback and cashback.amount > 0:
                cashback_applied = min(cashback.amount, total)
                total -= cashback_applied
                cashback.amount -= cashback_applied
                session.commit()

        await state.update_data(total=total, cashback_applied=cashback_applied)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(callback.from_user.id, "payment_cash"), callback_data="payment_cash")],
            [InlineKeyboardButton(text=get_text(callback.from_user.id, "payment_card"), callback_data="payment_card")]
        ])
        await callback.message.answer(
            get_text(callback.from_user.id, "choose_payment_method"),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.set_state(OrderConfirmation.payment_method)
        session.close()
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар handle_cashback_choice: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")
        await callback.answer()
        if 'session' in locals():
            session.close()
            

@dp.callback_query(lambda c: c.data in ["payment_cash", "payment_card"])
async def handle_payment_method(callback: types.CallbackQuery, state: FSMContext):
    try:
        session = Session()
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        profile = session.query(UserProfile).filter_by(telegram_id=callback.from_user.id).first()
        data = await state.get_data()
        total = data.get("total", 0.0)
        cashback_applied = data.get("cashback_applied", 0.0)
        cart_items_data = data.get("cart_items", [])

        # Барқарор кардани маълумоти сабад
        cart_items = []
        for cart_id, product_id, quantity in cart_items_data:
            cart_item = session.query(Cart).filter_by(id=cart_id).first()
            product = session.query(Product).filter_by(id=product_id).first()
            if cart_item and product:
                cart_items.append((cart_item, product))

        # Тасдиқи усули пардохт
        payment_method = "Нақд" if callback.data == "payment_cash" else "Корти бонкӣ"
        await callback.message.answer(
            get_text(callback.from_user.id, "payment_method_selected", method=payment_method),
            parse_mode="HTML"
        )

        # Коркарди фармоиш
        await process_order(callback, state, total, cart_items, user, profile, session, cashback_applied, payment_method)
        session.close()
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар handle_payment_method: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")
        await callback.answer()
        if 'session' in locals():
            session.close()
                                    

async def process_order(callback: types.CallbackQuery, state: FSMContext, total: float, cart_items: list, user, profile, session, cashback_applied: float = 0.0, payment_method: str = None):
    cashback_earned = total * 0.05
    cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
    if cashback:
        cashback.amount += cashback_earned
    else:
        cashback = Cashback(telegram_id=callback.from_user.id, amount=cashback_earned)
        session.add(cashback)
    session.commit()

    order_details = f"{get_text(callback.from_user.id, 'new_order')}\n\n"
    order_details += f"👤 {get_text(callback.from_user.id, 'user')}: {escape_html(user.first_name)} (@{escape_html(user.username or '')})\n"
    order_details += f"📞 {get_text(callback.from_user.id, 'phone')}: {escape_html(profile.phone_number)}\n"
    order_details += f"🍫 {get_text(callback.from_user.id, 'products')}:\n"
    for cart_item, product in cart_items:
        order = Order(
            telegram_id=callback.from_user.id,
            product_id=product.id,
            quantity=cart_item.quantity,
            total=product.price * cart_item.quantity
        )
        session.add(order)
        item_total = product.price * cart_item.quantity
        order_details += f"{escape_html(product.name)} x{cart_item.quantity} - {item_total:.2f} сомонī\n"

    order_details += f"\n💵 {get_text(callback.from_user.id, 'total')}: {total:.2f} сомонī\n"
    if cashback_applied > 0:
        order_details += f"💰 {get_text(callback.from_user.id, 'cashback_used').format(amount=cashback_applied)} сомонī\n"
    order_details += f"💰 {get_text(callback.from_user.id, 'cashback_earned')}: {cashback_earned:.2f} сомонī\n"
    if payment_method:
        order_details += f"💳 {get_text(callback.from_user.id, 'order_details_payment', method=payment_method)}\n"
    order_details += f"📅 {get_text(callback.from_user.id, 'date')}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

    session.query(Cart).filter(Cart.telegram_id == callback.from_user.id).delete()
    session.commit()

    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=order_details, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Хато дар фиристодани огоҳӣ ба гуруҳ: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "group_notification_error", error=str(e)), parse_mode="HTML")

    response = get_text(callback.from_user.id, "order_confirmed")
    if cashback_applied > 0:
        response += f"\n{get_text(callback.from_user.id, 'cashback_used').format(amount=cashback_applied)} сомонī"
    if payment_method:
        response += f"\n{get_text(callback.from_user.id, 'order_details_payment', method=payment_method)}"
    await callback.message.answer(response, parse_mode="HTML")
    

@dp.message(lambda message: message.text == get_text(message.from_user.id, "profile"))
async def setup_profile(message: types.Message, state: FSMContext):
    try:
        session = Session()
        profile = session.query(UserProfile).filter_by(telegram_id=message.from_user.id).first()
        session.close()

        if profile:
            response = f"Профили шумо:\nРақами телефон: {escape_html(profile.phone_number)}\nСуроға: {escape_html(profile.address)}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Тағйир додан", callback_data="edit_profile")],
                    [InlineKeyboardButton(text="Ба менюи асосӣ", callback_data="back_to_main")]
                ]
            )
            await message.answer(response, reply_markup=keyboard)
        else:
            await message.answer(get_text(message.from_user.id, "enter_new_phone"))
            await state.set_state(ProfileForm.phone)
    except Exception as e:
        logger.error(f"Хато дар setup_profile: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))

@dp.callback_query(lambda c: c.data == "edit_profile")
async def edit_profile(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(get_text(callback.from_user.id, "enter_new_phone"))
    await state.set_state(ProfileForm.phone)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    try:
        # Истифода аз get_main_keyboard барои гирифтани клавиатураи асосӣ бо тарҷумаҳои дуруст
        keyboard = get_main_keyboard(callback.from_user.id)
        await callback.message.answer(
            text="✅ Ба менюи асосӣ баргаштед:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар back_to_main: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")

@dp.message(ProfileForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    # Тоза кардани рамзҳои ғайрирақамӣ (+, -, бошгоҳ)
    cleaned_phone = ''.join(filter(str.isdigit, phone))
    # Агар рақам бо +992 оғоз шавад, онро тоза кунем
    if cleaned_phone.startswith("992"):
        cleaned_phone = cleaned_phone[3:]
    # Проверка, что номер состоит из 9 цифр
    if not cleaned_phone.isdigit() or len(cleaned_phone) != 9:
        await message.answer(
            get_text(
                message.from_user.id,
                "invalid_phone",
                error="Рақами телефон бояд 9 рақам бошад (масалан, 900585249)! "
                      "Лутфан бе +992 ворид кунед."
            )
        )
        return
    await state.update_data(phone=cleaned_phone)
    await message.answer(get_text(message.from_user.id, "enter_address"))
    await state.set_state(ProfileForm.address)

@dp.message(ProfileForm.address)
async def process_address(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        phone = data["phone"]
        address = message.text
        session = Session()
        profile = session.query(UserProfile).filter_by(telegram_id=message.from_user.id).first()
        if profile:
            profile.phone_number = phone
            profile.address = address
        else:
            profile = UserProfile(telegram_id=message.from_user.id, phone_number=phone, address=message.text)
            session.add(profile)
        session.commit()
        session.close()
        await message.answer("✅ Профил навсозӣ шуд!")
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=get_text(message.from_user.id, "menu")), KeyboardButton(text=get_text(message.from_user.id, "cart"))],
                [KeyboardButton(text=get_text(message.from_user.id, "profile")), KeyboardButton(text=get_text(message.from_user.id, "cashback"))],
                [KeyboardButton(text=get_text(message.from_user.id, "order_history")), KeyboardButton(text="address"), KeyboardButton(text="contacts")]
            ] + [[KeyboardButton(text=get_text(message.from_user.id, "admin_panel"))] if is_admin(message.from_user.id) else []],
            resize_keyboard=True
        )
        await message.answer("Ба менюи асосӣ:", reply_markup=keyboard)
        await state.clear()
    except Exception as e:
        logger.error(f"Хато дар process_address: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        await state.clear()

@dp.message(lambda message: message.text == get_text(message.from_user.id, "cashback"))
async def check_cashback(message: types.Message):
    try:
        session = Session()
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()

        if not user or not user.language:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🇹🇯 Тоҷикӣ", callback_data="set_language_tj"),
                        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_language_ru"),
                        InlineKeyboardButton(text="🇬🇧 English", callback_data="set_language_en")
                    ]
                ]
            )
            await message.answer(get_text(message.from_user.id, "choose_language"), reply_markup=keyboard)
            session.close()
            return

        cashback = session.query(Cashback).filter_by(telegram_id=message.from_user.id).first()
        session.close()
        await message.answer(f"<b>{get_text(message.from_user.id, 'cashback')}:</b> {cashback.amount if cashback else 0.0} сомонӣ", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Хато дар check_cashback: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data == "use_cashback")
async def use_cashback(callback: types.CallbackQuery):
    try:
        with Session() as session:
            cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
            cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == callback.from_user.id).all()

            if not cart_items:
                await callback.message.answer(get_text(callback.from_user.id, "cart_empty"))
                await callback.answer()
                return

            total = sum(product.price * cart_item.quantity for cart_item, product in cart_items)

            if not cashback or cashback.amount == 0:
                await callback.message.answer("Шумо кэшбэк надоред!")
                await callback.answer()
                return

            if cashback.amount >= total:
                cashback.amount -= total
                total = 0
            else:
                total -= cashback.amount
                cashback.amount = 0

            updated_cashback_amount = cashback.amount

            session.commit()

        await callback.message.answer(
            f"<b>Кэшбэк истифода шуд!</b>\nБақияи нав: {updated_cashback_amount} сомонӣ\nМаблағи боқимонда: {total} сомонӣ",
            parse_mode="HTML"
        )
        await view_cart(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар use_cashback: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.message(lambda message: message.text == get_text(message.from_user.id, "admin_panel"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(get_text(message.from_user.id, "no_access"))
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(message.from_user.id, "add_product"), callback_data="admin_add_product"),
                InlineKeyboardButton(text=get_text(message.from_user.id, "delete_product"), callback_data="admin_delete_product")
            ],
            [
                InlineKeyboardButton(text=get_text(message.from_user.id, "admin_update_product"), callback_data="admin_update_product")
            ],
            [
                InlineKeyboardButton(text=get_text(message.from_user.id, "add_order"), callback_data="admin_add_order"),
                InlineKeyboardButton(text=get_text(message.from_user.id, "view_orders"), callback_data="admin_view_orders")
            ],
            [
                InlineKeyboardButton(text=get_text(message.from_user.id, "manage_categories"), callback_data="admin_manage_categories")
            ],
            [
                InlineKeyboardButton(text=get_text(message.from_user.id, "back_to_main"), callback_data="back_to_main")
            ]
        ]
    )
    await message.answer(
        f"<b>{get_text(message.from_user.id, 'admin_panel')}</b>\n{get_text(message.from_user.id, 'select_action')}:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "admin_panel")
async def back_to_admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Иловаи Маҳсулот", callback_data="admin_add_product"),
                InlineKeyboardButton(text="🗑 Ҳазфи Маҳсулот", callback_data="admin_delete_product")
            ],
            [
                InlineKeyboardButton(text="📦 Иловаи Фармоиш", callback_data="admin_add_order"),
                InlineKeyboardButton(text="📜 Рӯйхати Фармоишҳо", callback_data="admin_view_orders")
            ],
            [
                InlineKeyboardButton(text="📋 Идоракунии Категорияҳо", callback_data="admin_manage_categories")
            ],
            [
                InlineKeyboardButton(text="🔙 Ба Менюи Асосӣ", callback_data="back_to_main")
            ]
        ]
    )
    await callback.message.answer(
        f"<b>{get_text(callback.from_user.id, 'admin_panel')}</b>\nИнтихоб кунед амали дилхоҳро аз менюи зер:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_manage_categories")
async def admin_manage_categories(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Эҷоди Категория", callback_data="admin_add_category"),
                InlineKeyboardButton(text="🗑 Ҳазфи Категория", callback_data="admin_delete_category")
            ],
            [
                InlineKeyboardButton(text="✏️ Таҳрири Категория", callback_data="admin_edit_category")
            ],
            [
                InlineKeyboardButton(text="🔙 Ба Панели Админ", callback_data="admin_panel")
            ]
        ]
    )
    await callback.message.answer(
        f"<b>{get_text(callback.from_user.id, 'manage_categories')}</b>\nИнтихоб кунед амали дилхоҳро барои идоракунии категорияҳо:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_add_product")
async def admin_add_product(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        return
    await callback.message.answer("Номи маҳсулотро ворид кун:")
    await state.set_state(AdminProductForm.name)
    await callback.answer()

@dp.message(AdminProductForm.name)
async def process_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Тавсифи маҳсулотро ворид кунед:")
    await state.set_state(AdminProductForm.description)

@dp.message(AdminProductForm.description)
async def process_product_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Нархи маҳсулотро ворид кунед (масалан, 10.5):")
    await state.set_state(AdminProductForm.price)

@dp.message(AdminProductForm.price)
async def process_product_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        
        # Гирифтани рӯйхати категорияҳо
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await message.answer("Ягон категория мавҷуд нест! Лутфан, аввал категория эҷод кунед.")
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Эҷоди категория", callback_data="admin_add_category")],
                    [InlineKeyboardButton(text=get_text(message.from_user.id, "back_to_admin"), callback_data="admin_panel")]
                ]
            )
            await message.answer(get_text(message.from_user.id, "next_action"), reply_markup=keyboard)
            return

        # Сохтани тугмаҳо барои интихоби категория
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=category.name, callback_data=f"select_category_{category.id}")]
                for category in categories
            ]
        )
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Эҷоди категорияи нав", callback_data="admin_add_category")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=get_text(message.from_user.id, "back_to_admin"), callback_data="admin_panel")])

        await message.answer("Категорияро аз рӯйхат интихоб кунед:", reply_markup=keyboard)
        await state.set_state(AdminProductForm.category)
    except ValueError:
        await message.answer("Лутфан, нархи дурустро ворид кунед (масалан, 10.5):")

@dp.callback_query(lambda c: c.data.startswith("select_category_"))
async def process_category_selection(callback: types.CallbackQuery, state: FSMContext):
    try:
        category_id = int(callback.data.split("_")[-1])
        session = Session()
        category = session.query(Category).filter_by(id=category_id).first()
        session.close()

        if not category:
            await callback.message.answer(get_text(callback.from_user.id, "no_categories"))
            await callback.answer()
            return

        await state.update_data(category_id=category_id)
        await callback.message.answer("Тасвири маҳсулотро бор кунед (ё барои гузаштан /skip ворид кунед):")
        await state.set_state(AdminProductForm.image)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар process_category_selection: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.message(AdminProductForm.image)
async def process_product_image(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        image_id = None
        if message.photo:
            image_id = message.photo[-1].file_id
        elif message.text != "/skip":
            await message.answer(get_text(message.from_user.id, "invalid_image"))
            return

        session = Session()
        name = escape_html(data["name"].strip())
        description = escape_html(data["description"].strip()) if data["description"] else None
        category_id = data["category_id"]

        product = Product(
            name=name,
            description=description,
            price=data["price"],
            category_id=category_id,
            image_id=image_id
        )
        session.add(product)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            await message.answer(f"Хато ҳангоми иловаи маҳсулот: {str(e)}")
            session.close()
            return

        session.close()

        await message.answer(get_text(message.from_user.id, "product_added", name=name), parse_mode="HTML")
        await state.clear()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text(message.from_user.id, "add_another_product"), callback_data="admin_add_product")],
                [InlineKeyboardButton(text=get_text(message.from_user.id, "back_to_admin"), callback_data="admin_panel")]
            ]
        )
        await message.answer(get_text(message.from_user.id, "next_action"), reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Хато дар process_product_image: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        await state.clear()
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data == "admin_delete_product")
async def admin_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return

    try:
        session = Session()
        products = session.query(Product).all()
        session.close()

        if not products:
            await callback.message.answer(get_text(callback.from_user.id, "product_not_found"))
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"{escape_html(product.name)} - {product.price} сомонī", callback_data=f"delete_product_{product.id}")]
                for product in products
            ]
        )
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Бозгашт ба панели админ", callback_data="admin_panel")])

        await callback.message.answer("Маҳсулотро барои ҳазф интихоб кунед:", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_delete_product: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_product_"))
async def confirm_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return

    try:
        product_id = int(callback.data.split("_")[-1])
        session = Session()
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            session.close()
            await callback.message.answer(get_text(callback.from_user.id, "product_not_found"))
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "yes_delete"), callback_data=f"confirm_delete_product_{product.id}")],
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "no_cancel"), callback_data="admin_delete_product")]
            ]
        )
        await callback.message.answer(
            get_text(callback.from_user.id, "confirm_delete_product", name=escape_html(product.name)),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар confirm_delete_product: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data.startswith("confirm_delete_product_"))
async def execute_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return

    try:
        product_id = int(callback.data.split("_")[-1])
        session = Session()
        product = session.query(Product).filter_by(id=product_id).first()

        if not product:
            session.close()
            await callback.message.answer(get_text(callback.from_user.id, "product_not_found"))
            await callback.answer()
            return

        session.query(Cart).filter_by(product_id=product.id).delete()
        session.query(Order).filter_by(product_id=product.id).delete()
        session.delete(product)
        session.commit()
        session.close()

        await callback.message.answer(get_text(callback.from_user.id, "product_deleted"), parse_mode="HTML")
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Ҳазфи маҳсулоти дигар", callback_data="admin_delete_product")],
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "back_to_admin"), callback_data="admin_panel")]
            ]
        )
        await callback.message.answer(get_text(callback.from_user.id, "next_action"), reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар execute_delete_product: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data == "admin_add_order")
async def admin_add_order(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        return
    try:
        session = Session()
        users = session.query(User).all()
        session.close()

        if not users:
            await callback.message.answer("Ягон корбар мавҷуд нест!")
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"{escape_html(user.first_name)} (@{escape_html(user.username or '')})", callback_data=f"admin_select_user_{user.telegram_id}")]
                for user in users
            ]
        )
        await callback.message.answer("Корбарро интихоб кунед:", reply_markup=keyboard)
        await state.set_state(AdminOrderForm.user)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_add_order: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_select_user_"))
async def admin_select_user(callback: types.CallbackQuery, state: FSMContext):
    try:
        user_id = int(callback.data.split("_")[-1])
        await state.update_data(user_id=user_id)
        session = Session()
        products = session.query(Product).all()
        session.close()

        if not products:
            await callback.message.answer(get_text(callback.from_user.id, "product_not_found"))
            await state.clear()
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"{escape_html(product.name)} - ${product.price}", callback_data=f"admin_select_product_{product.id}")]
                for product in products
            ]
        )
        await callback.message.answer("Маҳсулотро интихоб кунед:", reply_markup=keyboard)
        await state.set_state(AdminOrderForm.product)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_select_user: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data.startswith("admin_select_product_"))
async def admin_select_product(callback: types.CallbackQuery, state: FSMContext):
    try:
        product_id = int(callback.data.split("_")[-1])
        await state.update_data(product_id=product_id)
        await callback.message.answer("Миқдори маҳсулотро ворид кунед:")
        await state.set_state(AdminOrderForm.quantity)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_select_product: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.message(AdminOrderForm.quantity)
async def process_order_quantity(message: types.Message, state: FSMContext):
    try:
        if not message.text.isdigit():
            await message.answer("Лутфан, миқдори дурустро ворид кунед (масалан, 2):")
            return
        quantity = int(message.text)
        if quantity <= 0:
            await message.answer("Миқдор бояд мусбат бошад!")
            return
        data = await state.get_data()
        session = Session()
        product = session.query(Product).filter_by(id=data["product_id"]).first()
        if not product:
            await message.answer(get_text(message.from_user.id, "product_not_found"))
            session.close()
            await state.clear()
            return

        order = Order(
            telegram_id=data["user_id"],
            product_id=data["product_id"],
            quantity=quantity,
            total=product.price * quantity
        )
        session.add(order)
        session.commit()
        session.close()

        await message.answer(
            f"Фармоиш барои корбар бо ID {data['user_id']} <b>илова шуд!</b>\n"
            f"Маҳсулот: {escape_html(product.name)}, Миқдор: {quantity}, Ҳамагӣ: {product.price * quantity} сомонī",
            parse_mode="HTML"
        )
        await state.clear()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Иловаи фармоиши дигар", callback_data="admin_add_order")],
                [InlineKeyboardButton(text=get_text(message.from_user.id, "back_to_admin"), callback_data="admin_panel")]
            ]
        )
        await message.answer(get_text(message.from_user.id, "next_action"), reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Хато дар process_order_quantity: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data == "admin_view_orders")
async def admin_view_orders(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return
    try:
        session = Session()
        orders = session.query(Order, User, Product).join(User).join(Product, Order.product_id == Product.id, isouter=True).all()
        session.close()

        if not orders:
            await callback.message.answer(get_text(callback.from_user.id, "no_orders_admin"), parse_mode="HTML")
            await callback.answer()
            return

        response = f"<b>{get_text(callback.from_user.id, 'order_list')}</b>\n\n"
        total_all_orders = 0.0
        for order, user, product in orders:
            product_name = escape_html(product.name) if product else get_text(callback.from_user.id, "product_deleted")
            order_total = order.total
            total_all_orders += order_total
            response += f"📦 {get_text(callback.from_user.id, 'order')} #{order.id}\n"
            response += f"👤 {get_text(callback.from_user.id, 'user')}: {escape_html(user.first_name)} (@{escape_html(user.username or '')})\n"
            response += f"🍫 {get_text(callback.from_user.id, 'product')}: {product_name}\n"
            response += f"🔢 {get_text(callback.from_user.id, 'quantity')}: {order.quantity}\n"
            response += f"💵 {get_text(callback.from_user.id, 'total')}: {order_total:.2f} сомонӣ\n"
            response += f"📅 {get_text(callback.from_user.id, 'date')}: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        response += f"📊 <b>{get_text(callback.from_user.id, 'total_all_orders')}</b>: {total_all_orders:.2f} сомонӣ\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "back_to_admin"), callback_data="admin_panel")]
            ]
        )
        await callback.message.answer(response, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_view_orders: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_add_category")
async def admin_add_category(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return
    try:
        await callback.message.answer("Номи категорияро ворид кунед (масалан, Десерт):")
        await state.set_state(AdminCategoryForm.name)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_add_category: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.message(AdminCategoryForm.name)
async def process_category_name(message: types.Message, state: FSMContext):
    try:
        category_name = message.text.strip()
        if not category_name:
            await message.answer("Ном набояд холӣ бошад! Лутфан, номи дурустро ворид кунед:")
            return

        session = Session()
        existing_category = session.query(Category).filter_by(name=category_name).first()
        if existing_category:
            session.close()
            await message.answer(f"Категорияи '{escape_html(category_name)}' аллакай мавҷуд аст!")
            return

        await state.update_data(name=category_name)
        await message.answer("Тасвири категорияро бор кунед (ё барои гузаштан /skip ворид кунед):")
        await state.set_state(AdminCategoryForm.image)
        session.close()
    except Exception as e:
        logger.error(f"Хато дар process_category_name: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        if 'session' in locals():
            session.close()

@dp.message(AdminCategoryForm.image)
async def process_category_image(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        category_name = data["name"]
        image_id = None

        if message.photo:
            image_id = message.photo[-1].file_id
        elif message.text != "/skip":
            await message.answer(get_text(message.from_user.id, "invalid_image"))
            return

        session = Session()
        new_category = Category(name=category_name, image_id=image_id)
        session.add(new_category)
        session.commit()
        session.close()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Эҷоди категорияи дигар", callback_data="admin_add_category")],
                [InlineKeyboardButton(text="Ба идоракунии категорияҳо", callback_data="admin_manage_categories")],
                [InlineKeyboardButton(text=get_text(message.from_user.id, "back_to_admin"), callback_data="admin_panel")]
            ]
        )
        await message.answer(
            f"<b>Категорияи '{escape_html(category_name)}'</b> бомуваффақият эҷод шуд!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Хато дар process_category_image: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        if 'session' in locals():
            session.close()
        await state.clear()
        

@dp.callback_query(lambda c: c.data == "admin_delete_category")
async def admin_delete_category(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await callback.message.answer(get_text(callback.from_user.id, "no_categories"))
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=category.name, callback_data=f"delete_category_{category.id}")]
                for category in categories
            ]
        )
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Бозгашт ба идоракунии категорияҳо", callback_data="admin_manage_categories")])

        await callback.message.answer("<b>Категорияро барои ҳазф интихоб кунед:</b>", reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_delete_category: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_category_"))
async def confirm_delete_category(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer(get_text(callback.from_user.id, "no_access"))
        await callback.answer()
        return
    try:
        category_id = int(callback.data.split("_")[-1])
        session = Session()
        category = session.query(Category).filter_by(id=category_id).first()

        if not category:
            session.close()
            await callback.message.answer("Категория ёфт нашуд!")
            await callback.answer()
            return

        products = session.query(Product).filter_by(category_id=category_id).all()
        for product in products:
            product.category_id = None

        session.delete(category)
        session.commit()
        session.close()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Ҳазфи категорияи дигар", callback_data="admin_delete_category")],
                [InlineKeyboardButton(text="Ба идоракунии категорияҳо", callback_data="admin_manage_categories")],
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "back_to_admin"), callback_data="admin_panel")]
            ]
        )
        await callback.message.answer(
            f"<b>Категорияи '{escape_html(category.name)}'</b> ҳазф шуд ва маҳсулот ба категорияи пешфарз гузаронида шуданд!",
            reply_markup=keyboard, parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар confirm_delete_category: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()


@dp.callback_query(lambda c: c.data.startswith("view_product_"))
async def view_product(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data.split("_")[-1])
        session = Session()
        product = session.query(Product).filter_by(id=product_id).first()
        session.close()

        if not product:
            await callback.message.answer(get_text(callback.from_user.id, "product_not_found"))
            await callback.answer()
            return

        caption = (
            f"<b>{escape_html(product.name)}</b>\n"
            f"{escape_html(product.description or 'Тавсиф мавҷуд нест')}\n"
            f"💵 {get_text(callback.from_user.id, 'price')}: {product.price} сомонӣ"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=get_text(callback.from_user.id, "add_to_cart_button", name=escape_html(product.name)),
                callback_data=f"add_to_cart_{product.id}"
            )],
            [InlineKeyboardButton(
                text=get_text(callback.from_user.id, "back_to_categories"),
                callback_data="back_to_menu"
            )]
        ])

        await callback.message.answer(caption, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.error(f"Хато дар view_product: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()
            
@dp.message(lambda message: message.text == get_text(message.from_user.id, "feedback"))
async def request_feedback(message: types.Message, state: FSMContext):
    try:
        await message.answer(get_text(message.from_user.id, "send_feedback"))
        await state.set_state(FeedbackForm.feedback_text)
    except Exception as e:
        logger.error(f"Хато дар request_feedback: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))

@dp.message(FeedbackForm.feedback_text)
async def process_feedback(message: types.Message, state: FSMContext):
    try:
        feedback_text = message.text.strip()
        if not feedback_text:
            await message.answer(get_text(message.from_user.id, "feedback_empty"))
            return

        session = Session()
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        session.close()

        feedback_notification = get_text(
            message.from_user.id,
            "feedback_notification",
            first_name=escape_html(user.first_name or ""),
            username=escape_html(user.username or ""),
            feedback_text=escape_html(feedback_text),
            date=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        )

        try:
            await bot.send_message(chat_id=GROUP_CHAT_ID, text=feedback_notification, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Хато дар фиристодани фикру мулоҳиза ба гуруҳ: {str(e)}")
            await message.answer(get_text(message.from_user.id, "group_notification_error", error=str(e)), parse_mode="HTML")

        response = (
            f"{get_text(message.from_user.id, 'feedback_sent')}\n\n"
            f"📌 Мо фикру мулоҳизаи шуморо барои беҳтар кардани хизматрасониҳо истифода мебарем!\n"
            f"Чиро навбатӣ интихоб мекунед?"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(message.from_user.id, "menu"), callback_data="back_to_menu")],
            [InlineKeyboardButton(text=get_text(message.from_user.id, "cart"), callback_data="view_cart")],
            [InlineKeyboardButton(text=get_text(message.from_user.id, "back_to_main"), callback_data="back_to_main")]
        ])
        await message.answer(response, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
    except Exception as e:
        logger.error(f"Хато дар process_feedback: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        await state.clear()                                


@dp.callback_query(lambda c: c.data == "show_address")
async def show_address(callback: types.CallbackQuery):
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(callback.from_user.id, "back_to_main"), callback_data="back_to_main")]
        ])
        await callback.message.answer(
            get_text(callback.from_user.id, "address_text"),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар show_address: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")
        await callback.answer()

@dp.callback_query(lambda c: c.data == "show_contacts")
async def show_contacts(callback: types.CallbackQuery):
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 WhatsApp (+992900585249)", url="https://wa.me/+992900585249")],
            [InlineKeyboardButton(text="📱 WhatsApp (+992877808002)", url="https://wa.me/+992877808002")],
            [InlineKeyboardButton(text=get_text(callback.from_user.id, "back_to_main"), callback_data="back_to_main")]
        ])
        await callback.message.answer(
            get_text(callback.from_user.id, "contacts_text"),
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар show_contacts: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")
        await callback.answer()
        

@dp.callback_query(lambda c: c.data == "admin_update_product")
async def show_products_to_update(callback: types.CallbackQuery):
    try:
        session = Session()
        products = session.query(Product).all()
        if not products:
            await callback.message.answer(get_text(callback.from_user.id, "no_products"))
            session.close()
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{product.name} ({product.price} сомонӣ)", callback_data=f"update_product_{product.id}")]
            for product in products
        ])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=get_text(callback.from_user.id, "back_to_main"), callback_data="back_to_main")])
        
        await callback.message.answer(get_text(callback.from_user.id, "select_product_to_update"), reply_markup=keyboard)
        session.close()
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар show_products_to_update: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        
@dp.callback_query(lambda c: c.data.startswith("update_product_"))
async def start_update_product(callback: types.CallbackQuery, state: FSMContext):
    try:
        product_id = int(callback.data.split("_")[-1])
        await state.update_data(product_id=product_id)
        await callback.message.answer(get_text(callback.from_user.id, "update_product_name"))
        await state.set_state(UpdateProductForm.name)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар start_update_product: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.message(UpdateProductForm.name)
async def process_product_name(message: types.Message, state: FSMContext):
    try:
        await state.update_data(name=message.text.strip())
        await message.answer(get_text(message.from_user.id, "update_product_description"))
        await state.set_state(UpdateProductForm.description)
    except Exception as e:
        logger.error(f"Хато дар process_product_name: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))

@dp.message(UpdateProductForm.description)
async def process_product_description(message: types.Message, state: FSMContext):
    try:
        if message.text == get_text(message.from_user.id, "skip"):
            await state.update_data(description=None)
        else:
            await state.update_data(description=message.text.strip())
        await message.answer(get_text(message.from_user.id, "update_product_price"))
        await state.set_state(UpdateProductForm.price)
    except Exception as e:
        logger.error(f"Хато дар process_product_description: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))

@dp.message(UpdateProductForm.price)
async def process_product_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            await message.answer(get_text(message.from_user.id, "invalid_price"))
            return
        await state.update_data(price=price)
        
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await message.answer(get_text(message.from_user.id, "no_categories"))
            await state.clear()
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=category.name, callback_data=f"update_category_{category.id}")]
            for category in categories
        ])
        await message.answer(get_text(message.from_user.id, "update_product_category"), reply_markup=keyboard)
        await state.set_state(UpdateProductForm.category)
    except ValueError:
        await message.answer(get_text(message.from_user.id, "invalid_price"))
    except Exception as e:
        logger.error(f"Хато дар process_product_price: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))

@dp.callback_query(lambda c: c.data.startswith("update_category_"))
async def process_product_category(callback: types.CallbackQuery, state: FSMContext):
    try:
        category_id = int(callback.data.split("_")[-1])
        await state.update_data(category_id=category_id)
        await callback.message.answer(
            get_text(callback.from_user.id, "update_product_image"),
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=get_text(callback.from_user.id, "skip"))]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        await state.set_state(UpdateProductForm.image)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар process_product_category: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()

@dp.message(UpdateProductForm.image)
async def process_product_image(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        product_id = data["product_id"]
        name = data["name"]
        description = data["description"]
        price = data["price"]
        category_id = data["category_id"]
        image_id = None

        if message.text == get_text(message.from_user.id, "skip"):
            image_id = None
        elif message.photo and message.photo[-1].file_id:
            image_id = message.photo[-1].file_id
        else:
            await message.answer(get_text(message.from_user.id, "error"))
            return

        session = Session()
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            await message.answer(get_text(message.from_user.id, "error"))
            session.close()
            await state.clear()
            return

        product.name = name
        product.description = description
        product.price = price
        product.category_id = category_id
        if image_id:
            product.image_id = image_id

        session.commit()
        session.close()

        await message.answer(
            get_text(message.from_user.id, "product_updated"),
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Хато дар process_product_image: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        await state.clear()
        
        
        
@dp.message(lambda message: message.text == get_text(message.from_user.id, "contact_info"))
async def contact_info(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(message.from_user.id, "address"), callback_data="show_address")],
        [InlineKeyboardButton(text=get_text(message.from_user.id, "contacts"), callback_data="show_contacts")]
    ])
    await message.answer(get_text(message.from_user.id, "choose_contact_info"), reply_markup=keyboard)

   
                                

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())