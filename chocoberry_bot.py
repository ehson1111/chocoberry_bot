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
    
class OrderConfirmation(StatesGroup):
    confirm_cashback = State()    

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
        "cashback_used": "Кэшбэк дар ҳаҷми ${amount:.2f} истифода шуд!",
        "cashback_available": "Шумо ${amount:.2f} кэшбэк доред. Оё мехоҳед онро истифода баред?",
        "use_cashback": "Истифодаи кэшбэк",
        "skip_cashback": "Бе кэшбэк идома диҳед",
        "cashback_used": "Кэшбэк дар ҳаҷми ${amount:.2f} истифода шуд!",
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
        "cashback_used": "Кэшбэк в размере ${amount:.2f} использован!",
        "cashback_available": "У вас есть ${amount:.2f} кэшбэка. Хотите использовать?",
        "use_cashback": "Использовать кэшбэк",
        "skip_cashback": "Продолжить без кэшбэка",
        "cashback_used": "Кэшбэк в размере ${amount:.2f} использован!",
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
        "cashback_used": "Cashback of ${amount:.2f} has been used!",
        "cashback_available": "You have ${amount:.2f} cashback. Would you like to use it?",
        "use_cashback": "Use cashback",
        "skip_cashback": "Continue without cashback",
        "cashback_used": "Cashback of ${amount:.2f} has been used!",
    }
}

def get_text(user_id: int, key: str, **kwargs) -> str:
    session = Session()
    user = session.query(User).filter_by(telegram_id=user_id).first()
    language = user.language if user and user.language in TRANSLATIONS else "tj"
    session.close()
    text = TRANSLATIONS.get(language, TRANSLATIONS["tj"]).get(key, key)
    try:
        return text.format(**kwargs)
    except KeyError:
        logger.error(f"Хато дар форматкунии матн барои калид '{key}' бо забон '{language}'")
        return text

def escape_html(text: str) -> str:
    if text is None:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

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
                await message.answer("Хато дар сабти корбар, лутфан дубора кӯшиш кунед!")
                session.close()
                return

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
    except Exception as e:
        logger.error(f"Хато дар start_command: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data.startswith("set_language_"))
async def set_language(callback: types.CallbackQuery):
    try:
        language = callback.data.split("_")[-1]
        if language not in ["tj", "ru", "en"]:
            await callback.message.answer("Неизвестный язык!")
            await callback.answer()
            return

        session = Session()
        user = session.query(User).filter_by(telegram_id=callback.from_user.id).first()
        if user:
            user.language = language
            session.commit()
        session.close()

        buttons = [
            [
                KeyboardButton(text=get_text(callback.from_user.id, "menu")),
                KeyboardButton(text=get_text(callback.from_user.id, "cart"))
            ],
            [
                KeyboardButton(text=get_text(callback.from_user.id, "profile")),
                KeyboardButton(text=get_text(callback.from_user.id, "cashback"))
            ],
            [
                KeyboardButton(text=get_text(callback.from_user.id, "order_history")),
                KeyboardButton(text="address"),
                KeyboardButton(text="contacts")
            ]
        ]

        if is_admin(callback.from_user.id):
            buttons.append([KeyboardButton(text=get_text(callback.from_user.id, "admin_panel"))])

        keyboard = ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True
        )

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

@dp.message(lambda message: message.text in [TRANSLATIONS["tj"]["menu"], TRANSLATIONS["ru"]["menu"], TRANSLATIONS["en"]["menu"]])
async def show_menu(message: types.Message):
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await message.answer(get_text(message.from_user.id, "no_categories"))
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}")]
            for category in categories
        ])
        await message.answer(get_text(message.from_user.id, "choose_category"), reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Хато дар show_menu: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))

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
            response += f"{escape_html(product.name)} x{cart_item.quantity} - ${item_total}\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="➕", callback_data=f"increase_quantity_{cart_item.id}"),
                InlineKeyboardButton(text="➖", callback_data=f"decrease_quantity_{cart_item.id}"),
                InlineKeyboardButton(text="🗑 Хориҷ", callback_data=f"remove_from_cart_{cart_item.id}")
            ])

        response += f"<b>Ҳамагӣ:</b> ${total}\n"
        response += f"<b>Кэшбэки дастрас:</b> ${cashback.amount if cashback else 0.0}\n"
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
            await callback.message.answer("Миқдор зиёд карда шуд!")
            await view_cart(callback.message)
        else:
            await callback.message.answer("Ашё дар сабад ёфт нашуд!")
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
                await callback.message.answer("Миқдор кам карда шуд!")
            else:
                session.delete(cart_item)
                session.commit()
                await callback.message.answer("Ашё аз сабад хориҷ шуд!")
            await view_cart(callback.message)
        else:
            await callback.message.answer("Ашё дар сабад ёфт нашуд!")
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
            await callback.message.answer("Ашё аз сабад хориҷ шуд!")
            await view_cart(callback.message)
        else:
            await callback.message.answer("Ашё дар сабад ёфт нашуд!")
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
            response += f"{get_text(message.from_user.id, 'total')}: ${order.total}\n"
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
            await callback.message.answer(get_text(callback.from_user.id, "profile_missing"), parse_mode="HTML")
            await callback.answer()
            return

        # Ҳисоби маблағи умумӣ
        total = sum(product.price * cart_item.quantity for cart_item, product in cart_items)

        # Санҷиши тавозуни кэшбэк
        cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
        if not cashback:
            cashback = Cashback(telegram_id=callback.from_user.id, amount=0.0)
            session.add(cashback)
            session.commit()

        # Агар кэшбэк мавҷуд бошад, аз корбар пурсем, ки оё мехоҳад истифода кунад
        if cashback.amount > 0:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "use_cashback"), callback_data="apply_cashback")],
                [InlineKeyboardButton(text=get_text(callback.from_user.id, "skip_cashback"), callback_data="skip_cashback")]
            ])
            await callback.message.answer(
                f"{get_text(callback.from_user.id, 'cashback_available', amount=cashback.amount)}\n"
                f"{get_text(callback.from_user.id, 'total')}: ${total:.2f}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            # Нигоҳ доштани маблағи умумӣ ва маълумоти сабад дар FSM
            await state.update_data(total=total, cart_items=[(item.id, product.id, item.quantity) for item, product in cart_items])
            await state.set_state(OrderConfirmation.confirm_cashback)
            session.close()
            await callback.answer()
            return

        # Агар кэшбэк набошад, мустақиман фармоишро идома диҳем
        await process_order(callback, state, total, cart_items, user, profile, session)
        session.close()
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

        # Барқарор кардани маълумоти сабад
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
                cashback_applied = min(cashback.amount, total)  # Истифодаи кэшбэк то маблағи умумӣ
                total -= cashback_applied
                cashback.amount -= cashback_applied
                session.commit()

        await process_order(callback, state, total, cart_items, user, profile, session, cashback_applied)
        session.close()
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар handle_cashback_choice: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"), parse_mode="HTML")
        await callback.answer()
        if 'session' in locals():
            session.close()

async def process_order(callback: types.CallbackQuery, state: FSMContext, total: float, cart_items: list, user, profile, session, cashback_applied: float = 0.0):
    # Ҳисоби кэшбэки нав
    cashback_earned = total * 0.05  # 5% кэшбэк аз маблағи ниҳоӣ
    cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
    if cashback:
        cashback.amount += cashback_earned
    else:
        cashback = Cashback(telegram_id=callback.from_user.id, amount=cashback_earned)
        session.add(cashback)
    session.commit()

    # Эҷоди тафсилоти фармоиш
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
        order_details += f"{escape_html(product.name)} x{cart_item.quantity} - ${item_total:.2f}\n"

    order_details += f"\n💵 {get_text(callback.from_user.id, 'total')}: ${total:.2f}\n"
    if cashback_applied > 0:
        order_details += f"💰 {get_text(callback.from_user.id, 'cashback_used')}: ${cashback_applied:.2f}\n"
    order_details += f"💰 {get_text(callback.from_user.id, 'cashback_earned')}: ${cashback_earned:.2f}\n"
    order_details += f"📅 {get_text(callback.from_user.id, 'date')}: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

    # Тоза кардани сабад
    session.query(Cart).filter(Cart.telegram_id == callback.from_user.id).delete()
    session.commit()

    # Фиристодани огоҳинома ба гуруҳ
    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=order_details, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Хато дар фиристодани огоҳӣ ба гуруҳ: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "group_notification_error", error=str(e)), parse_mode="HTML")

    # Паём ба корбар
    response = get_text(callback.from_user.id, "order_confirmed")
    if cashback_applied > 0:
        response += f"\n{get_text(callback.from_user.id, 'cashback_used')}: ${cashback_applied:.2f}"
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
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(callback.from_user.id, "menu")), KeyboardButton(text=get_text(callback.from_user.id, "cart"))],
            [KeyboardButton(text=get_text(callback.from_user.id, "profile")), KeyboardButton(text=get_text(callback.from_user.id, "cashback"))],
            [KeyboardButton(text=get_text(callback.from_user.id, "order_history")), KeyboardButton(text="address"), KeyboardButton(text="contacts")]
        ] + [[KeyboardButton(text=get_text(callback.from_user.id, "admin_panel"))] if is_admin(callback.from_user.id) else []],
        resize_keyboard=True
    )
    await callback.message.answer("✅ Ба менюи асосӣ баргаштед:", reply_markup=keyboard)
    await callback.answer()

@dp.message(ProfileForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Лутфан, суроғаро ворид кунед:")
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
        await message.answer(f"<b>{get_text(message.from_user.id, 'cashback')}:</b> ${cashback.amount if cashback else 0.0}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Хато дар check_cashback: {str(e)}")
        await message.answer(get_text(message.from_user.id, "error"))
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data == "use_cashback")
async def use_cashback(callback: types.CallbackQuery):
    try:
        session = Session()
        cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
        cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == callback.from_user.id).all()

        if not cart_items:
            session.close()
            await callback.message.answer(get_text(callback.from_user.id, "cart_empty"))
            await callback.answer()
            return

        total = sum(product.price * cart_item.quantity for cart_item, product in cart_items)

        if not cashback or cashback.amount == 0:
            session.close()
            await callback.message.answer("Шумо кэшбэк надоред!")
            await callback.answer()
            return

        if cashback.amount >= total:
            cashback.amount -= total
            total = 0
        else:
            total -= cashback.amount
            cashback.amount = 0

        session.commit()
        session.close()

        await callback.message.answer(f"<b>Кэшбэк истифода шуд!</b>\nБақияи нав: ${cashback.amount}\nМаблағи боқимонда: ${total}", parse_mode="HTML")
        await view_cart(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар use_cashback: {str(e)}")
        await callback.message.answer(get_text(callback.from_user.id, "error"))
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.message(lambda message: message.text == get_text(message.from_user.id, "admin_panel"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer(get_text(message.from_user.id, "no_access"))
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
    await message.answer(
        f"<b>{get_text(message.from_user.id, 'admin_panel')}</b>\nИнтихоб кунед амали дилхоҳро аз менюи зер:",
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
        await message.answer("Категорияи маҳсулотро ворид кунед (масалан, Десерт):")
        await state.set_state(AdminProductForm.category)
    except ValueError:
        await message.answer("Лутфан, нархи дурустро ворид кунед (масалан, 10.5):")

@dp.message(AdminProductForm.category)
async def process_product_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("Тасвири маҳсулотро бор кунед (ё барои гузаштан /skip ворид кунед):")
    await state.set_state(AdminProductForm.image)

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
        category_name = escape_html(data["category"].strip())

        category = session.query(Category).filter_by(name=category_name).first()
        if not category:
            category = Category(name=category_name)
            session.add(category)
            session.commit()

        product = Product(
            name=name,
            description=description,
            price=data["price"],
            category_id=category.id,
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
                [InlineKeyboardButton(text=f"{escape_html(product.name)} - ${product.price}", callback_data=f"delete_product_{product.id}")]
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
            f"Маҳсулот: {escape_html(product.name)}, Миқдор: {quantity}, Ҳамагӣ: ${product.price * quantity}",
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
            response += f"💵 {get_text(callback.from_user.id, 'total')}: ${order_total:.2f}\n"
            response += f"📅 {get_text(callback.from_user.id, 'date')}: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        response += f"📊 <b>{get_text(callback.from_user.id, 'total_all_orders')}</b>: ${total_all_orders:.2f}\n"

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
            await state.clear()
            return

        new_category = Category(name=category_name)
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
        await message.answer(f"<b>Категорияи '{escape_html(category_name)}'</b> бомуваффақият эҷод шуд!", reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
    except Exception as e:
        logger.error(f"Хато дар process_category_name: {str(e)}")
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

@dp.message(lambda message: message.text == "address")
async def addresses(message: types.Message):
    await message.answer(get_text(message.from_user.id, "address"))

@dp.message(lambda message: message.text == "contacts")
async def contacts(message: types.Message):
    await message.answer(get_text(message.from_user.id, "contacts"))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())