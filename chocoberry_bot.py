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
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
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
    
# Иловаи маҳсулот




class AdminOrderForm(StatesGroup):
    user = State()
    product = State()
    quantity = State()

class AdminCategoryForm(StatesGroup):
    name = State()

# Функсияи тозакунӣ барои HTML
def escape_html(text: str) -> str:
    if text is None:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# Санҷиши админ
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# Фармони /start
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
                last_name=message.from_user.last_name or None
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
        session.close()

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🍫 Меню"), KeyboardButton(text="🛒 Сабад")],
                [KeyboardButton(text="👤 Профил"), KeyboardButton(text="💰 Кэшбэк")],
                [KeyboardButton(text="📜 Таърихи фармоишҳо"),KeyboardButton(text= "🏪 Адрес"),KeyboardButton(text="📞 Контакты")]
                
                
            ] + ([[KeyboardButton(text="🔧 Панели админ")] if is_admin(message.from_user.id) else []]),
            resize_keyboard=True
        )
        await message.answer("<b>🍫🍓 Хуш омадед ба ChocoBerry!</b>\nЯк амалро интихоб кунед:", reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Хато дар start_command: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        if 'session' in locals():
            session.close()
            

# Намоиши меню
@dp.message(lambda message: message.text == "🍫 Меню")
async def show_menu(message: types.Message):
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await message.answer("Ягон категория мавҷуд нест!")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}")]
            for category in categories
        ])
        await message.answer("📋 Категорияро интихоб кунед:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Хато дар show_menu: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")

# Намоиши маҳсулотҳои категория
@dp.callback_query(lambda c: c.data.startswith("category_"))
async def show_category_products(callback: types.CallbackQuery):
    try:
        category_id = int(callback.data.split("_")[-1])
        session = Session()
        category = session.query(Category).filter_by(id=category_id).first()
        products = session.query(Product).filter_by(category_id=category_id).all()
        session.close()

        if not category:
            await callback.message.answer("Категория ёфт нашуд!")
            await callback.answer()
            return

        response = f"🍫🍓 <b>{escape_html(category.name)}</b>\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for product in products:
            response += f"➡️ <b>{escape_html(product.name)}</b> - ${product.price}\n"
            response += f"<i>{escape_html(product.description or '')}</i>\n\n"
            if product.image_id:
                try:
                    await callback.message.answer_photo(
                        photo=product.image_id,
                        caption=f"<b>{escape_html(product.name)}</b>\n{escape_html(product.description or '')}\n💵 Нарх: ${product.price}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Хато ҳангоми фиристодани тасвир барои маҳсулот {product.name}: {str(e)}")
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"📥 Илова ба сабад: {escape_html(product.name)}",
                    callback_data=f"add_to_cart_{product.id}"
                )
            ])

        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Бозгашт ба категорияҳо", callback_data="back_to_categories")])
        await callback.message.answer(response, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар show_category_products: {str(e)}")
        await callback.message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await callback.answer()
        if 'session' in locals():
            session.close()

# Бозгашт ба категорияҳо
@dp.callback_query(lambda c: c.data == "back_to_categories")
async def back_to_categories(callback: types.CallbackQuery):
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await callback.message.answer("Ягон категория мавҷуд нест!")
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}")]
            for category in categories
        ])
        await callback.message.answer("📋 Категорияро интихоб кунед:", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар back_to_categories: {str(e)}")
        await callback.message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await callback.answer()

# Илова ба сабад
@dp.callback_query(lambda c: c.data.startswith("add_to_cart_"))
async def add_to_cart(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data.split("_")[-1])
        session = Session()
        cart_item = Cart(
            telegram_id=callback.from_user.id,
            product_id=product_id,
            quantity=1
        )
        session.add(cart_item)
        session.commit()
        session.close()
        await callback.message.answer("Ба сабад илова шуд!")
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар add_to_cart: {str(e)}")
        await callback.message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await callback.answer()
        if 'session' in locals():
            session.close()

# Намоиши сабад
@dp.message(lambda message: message.text == "🛒 Сабад")
async def view_cart(message: types.Message):
    try:
        session = Session()
        cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == message.from_user.id).all()
        profile = session.query(UserProfile).filter_by(telegram_id=message.from_user.id).first()
        cashback = session.query(Cashback).filter_by(telegram_id=message.from_user.id).first()
        session.close()

        if not cart_items:
            await message.answer("Сабади шумо холӣ аст!")
            return

        if not profile:
            await message.answer("Лутфан, аввал профили худро пур кунед (рақами телефон ва суроға)!")
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
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")

# Зиёд кардани миқдор
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
        await callback.message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await callback.answer()
        if 'session' in locals():
            session.close()

# Кам кардани миқдор
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
        await callback.message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await callback.answer()
        if 'session' in locals():
            session.close()

# Хориҷ аз сабад
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
        await callback.message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await callback.answer()
        if 'session' in locals():
            session.close()

# Таърихи фармоишҳо
@dp.message(lambda message: message.text == "📜 Таърихи фармоишҳо")
async def view_order_history(message: types.Message):
    try:
        session = Session()
        orders = session.query(Order, Product).join(Product, Order.product_id == Product.id, isouter=True).filter(Order.telegram_id == message.from_user.id).all()
        session.close()

        if not orders:
            await message.answer("Шумо ягон фармоиш надоред! 😔 Лутфан, маҳсулотро ба сабад илова кунед ва фармоиш диҳед.")
            return

        response = "<b>📜 Таърихи фармоишҳои шумо:</b>\n\n"
        for order, product in orders:
            product_name = escape_html(product.name) if product else "Маҳсулот хазф шудааст"
            response += f"Фармоиш #{order.id}\n"
            response += f"Маҳсулот: {product_name}\n"
            response += f"Миқдор: {order.quantity}\n"
            response += f"Ҳамагӣ: ${order.total}\n"
            response += f"Сана: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        try:
            await message.answer(response, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Хатои таҳлили HTML дар view_order_history: {str(e)}")
            await message.answer(response)  # Бе parse_mode
    except Exception as e:
        logger.error(f"Хато дар view_order_history: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед! 😞")
        if 'session' in locals():
            session.close()

# Тасдиқи фармоиш
@dp.callback_query(lambda c: c.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery):
    try:
        session = Session()
        # Санҷиши вуҷуди корбар
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
            await callback.message.answer("Сабади шумо хол! 🛒")
            await callback.answer()
            return

        if not profile:
            session.close()
            await callback.message.answer("Лутфан, аввал профили худро пур кунед! 📋")
            await callback.answer()
            return

        total = sum(product.price * cart_item.quantity for cart_item, product in cart_items)
        cashback_amount = total * 0.05

        order_details = "📦 Фармоиши нав:\n\n"
        order_details += f"👤 Корбар: {escape_html(user.first_name)} (@{escape_html(user.username or '')})\n"
        order_details += f"📞 Рақами телефон:: {escape_html(profile.phone_number)}\n"
        order_details += f"🏠 Суроға: {escape_html(profile.address)}\n"
        order_details += "🍫 Маҳсулотҳо:\n"
        for cart_item, product in cart_items:
            order = Order(
                telegram_id=callback.from_user.id,
                product_id=product.id,
                quantity=cart_item.quantity,
                total=product.price * cart_item.quantity
            )
            session.add(order)
            item_total = product.price * cart_item.quantity
            order_details += f"{escape_html(product.name)} x{cart_item.quantity} - ${item_total}\n"

        order_details += f"💵 Ҳамагӣ: ${total}\n"
        order_details += f"💰 Кэшбэки бадастоварда: ${cashback_amount}\n"
        order_details += f"📅 Сана: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

        cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
        if not cashback:
            cashback = Cashback(telegram_id=callback.from_user.id, amount=0.0)
            session.add(cashback)
        cashback.amount += cashback_amount

        session.query(Cart).filter(Cart.telegram_id == callback.from_user.id).delete()
        session.commit()
        session.close()

        try:
            await bot.send_message(chat_id=GROUP_CHAT_ID, text=order_details)
        except Exception as e:
            logger.error(f"Хато дар фиристодани огоҳӣ ба гуруҳ: {str(e)}")
            await callback.message.answer(f"Хато дар фиристодани огоҳӣ ба гуруҳ: {str(e)}")

        await callback.message.answer("<b>✅ Фармоиши шумо тасдиқ шуд!</b> Сабад хол карда шуд.", parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар confirm_order: {str(e)}")
        await callback.message.answer("Хато рух дод, лутфан дубора кӯшиш кунед! 😞")
        await callback.answer()
        if 'session' in locals():
            session.close()

# Профил
@dp.message(lambda message: message.text == "👤 Профил")
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
            await message.answer("Лутфан, рақами телефонаро ворид кунед:")
            await state.set_state(ProfileForm.phone)
    except Exception as e:
        logger.error(f"Хато дар setup_profile: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")

@dp.callback_query(lambda c: c.data == "edit_profile")
async def edit_profile(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Лутфан, раси нави телефонаро ворид кунед:")
    await state.set_state(ProfileForm.phone)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍫 Меню"), KeyboardButton(text="🛒 Сабад")],
            [KeyboardButton(text="👤 Профил"), KeyboardButton(text="💰 Кэшбэк")],
            [KeyboardButton(text="📜 Таърихи фармоишҳо")]
        ] + [[KeyboardButton(text="🔧 Панели админ")] if is_admin(callback.from_user.id) else []],
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
                [KeyboardButton(text="🍫 Меню"), KeyboardButton(text="🛒 Сабад")],
                [KeyboardButton(text="👤 Профил"), KeyboardButton(text="💰 Кэшбэк")],
                [KeyboardButton(text="📜 Таърихи фармоиш")]
            ] + [[KeyboardButton(text="🔧 Панели админ")] if is_admin(message.from_user.id) else []],
            resize_keyboard=True
        )
        await message.answer("Ба менюи асосӣ:", reply_markup=keyboard)
        await state.clear()
    except Exception as e:
        logger.error(f"Хато дар process_address: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора куш кунед!")
        await state.clear()

# Кэшбэк
@dp.message(lambda message: message.text == "💰 Кэшбэк")
async def check_cashback(message: types.Message):
    try:
        session = Session()
        cashback = session.query(Cashback).filter_by(telegram_id=message.from_user.id).first()
        session.close()
        await message.answer(f"<b>💰 Бақияи кэшбэки шумо:</b> ${cashback.amount if cashback else 0.0}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Хато дар check_cashback: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора куш кунед!")

@dp.callback_query(lambda c: c.data == "use_cashback")
async def use_cashback(callback: types.CallbackQuery):
    try:
        session = Session()
        cashback = session.query(Cashback).filter_by(telegram_id=callback.from_user.id).first()
        cart_items = session.query(Cart, Product).join(Product).filter(Cart.telegram_id == callback.from_user.id).all()

        if not cart_items:
            session.close()
            await callback.message.answer("Сабади шумо холӣ аст!")
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
        await callback.message.answer("Хато рух дод, лутфан дубора куш кунед!")
        await callback.answer()
        if 'session' in locals():
            session.close()

# Панели админ
@dp.message(lambda message: message.text == "🔧 Панели админ")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Шумо дастрасӣ ба панели админ надоред!")
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Иловаи маҳсулот", callback_data="admin_add_product")],
            [InlineKeyboardButton(text="Иловаи фармоиш", callback_data="admin_add_order")],
            [InlineKeyboardButton(text="Рӯйхати фармоишҳо", callback_data="admin_view_orders")],
            [InlineKeyboardButton(text="Ҳазфи маҳсулот", callback_data="admin_delete_product")],
            [InlineKeyboardButton(text="Идоракунии категорияҳо", callback_data="admin_manage_categories")]
        ]
    )
    await message.answer("<b>Панели админ:</b>", reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "admin_panel")
async def back_to_admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастрасї ба!")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Иловаи маҳсулот", callback_data="admin_add_product")],
            [InlineKeyboardButton(text="Иловаи фармоиш", callback_data="admin_add_order")],
            [InlineKeyboardButton(text="Рӯйхати фармоиш", callback_data="admin_view_orders")],
            [InlineKeyboardButton(text="Ҳазфи маҳсулот", callback_data="admin_delete_product")],
            [InlineKeyboardButton(text="Идоракунии категория", callback_data="admin_manage_categories")]
        ]
    )
    await callback.message.answer("<b>Панели админ:</b>", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_manage_categories")
async def admin_manage_categories(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастрасї ба!")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Эҷоди категория", callback_data="admin_add_category")],
            [InlineKeyboardButton(text="Ҳазфи категория", callback_data="admin_delete_category")],
            [InlineKeyboardButton(text="🔙 Бозгашт ба панели админ", callback_data="admin_panel")]
        ]
    )
    await callback.message.answer("<b>Идоракунии категория:</b>", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()



# Функсияи тозакунӣ барои HTML
def escape_html(text: str) -> str:
    if text is None:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# Иловаи маҳсулот
@dp.callback_query(lambda c: c.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастрасӣ ба панели админ надоред!")
        await callback.answer()
        return
    await callback.message.answer("Номи маҳсулотро ворид кунед:")
    await state.set_state(AdminProductForm.name)
    await callback.answer()

@dp.message(AdminProductForm.name)
async def process_product_name(message: Message, state: FSMContext):
    try:
        name = message.text.strip()
        if not name:
            await message.answer("Номи маҳсулот набояд холӣ бошад! Лутфан, номи дурустро ворид кунед:")
            return
        await state.update_data(name=name)
        await message.answer("Тавсифи маҳсулотро ворид кунед (ё /skip барои гузаштан):")
        await state.set_state(AdminProductForm.description)
    except Exception as e:
        logger.error(f"Хато дар process_product_name: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await state.clear()

@dp.message(AdminProductForm.description)
async def process_product_description(message: Message, state: FSMContext):
    try:
        description = None if message.text == "/skip" else message.text.strip()
        await state.update_data(description=description)
        await message.answer("Нархи маҳсулотро ворид кунед (масалан, 10.5):")
        await state.set_state(AdminProductForm.price)
    except Exception as e:
        logger.error(f"Хато дар process_product_description: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await state.clear()

@dp.message(AdminProductForm.price)
async def process_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            await message.answer("Нарх бояд мусбат бошад! Лутфан, нархи дурустро ворид кунед (масалан, 10.5):")
            return
        await state.update_data(price=price)
        await message.answer("Категорияи маҳсулотро ворид кунед (масалан, Десерт):")
        await state.set_state(AdminProductForm.category)
    except ValueError:
        await message.answer("Лутфан, нархи дурустро ворид кунед (масалан, 10.5):")
    except Exception as e:
        logger.error(f"Хато дар process_product_price: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await state.clear()

@dp.message(AdminProductForm.category)
async def process_product_category(message: Message, state: FSMContext):
    try:
        category_name = message.text.strip()
        if not category_name:
            await message.answer("Номи категория набояд холӣ бошад! Лутфан, номи дурустро ворид кунед:")
            return
        await state.update_data(category=category_name)
        await message.answer("Тасвири маҳсулотро бор кунед (ё барои гузаштан /skip ворид кунед):")
        await state.set_state(AdminProductForm.image)
    except Exception as e:
        logger.error(f"Хато дар process_product_category: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед!")
        await state.clear()

@dp.message(AdminProductForm.image)
async def process_product_image(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        image_id = None
        if message.photo:
            image_id = message.photo[-1].file_id
        elif message.text != "/skip":
            await message.answer("Лутфан, тасвир бор кунед ё /skip-ро истифода баред!")
            return

        session = Session()
        name = escape_html(data["name"])
        description = escape_html(data["description"]) if data["description"] else None
        category_name = escape_html(data["category"])

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
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Хатои такрори маҳсулот: {str(e)}")
            await message.answer(f"Маҳсулот бо номи '{name}' аллакай мавҷуд аст! Лутфан, номи дигар интихоб кунед.")
            await state.clear()
            session.close()
            return
        except Exception as e:
            session.rollback()
            logger.error(f"Хато ҳангоми иловаи маҳсулот: {str(e)}")
            await message.answer(f"Хато ҳангоми иловаи маҳсулот: {str(e)}")
            await state.clear()
            session.close()
            return

        session.close()
        await message.answer(f"Маҳсулот '<b>{escape_html(name)}</b>' бомуваффақият илова шуд! ✅", parse_mode="HTML")
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Иловаи маҳсулоти дигар", callback_data="admin_add_product")],
                [InlineKeyboardButton(text="Ба панели админ", callback_data="admin_panel")]
            ]
        )
        await message.answer("Амали навбатӣ:", reply_markup=keyboard)
        await state.clear()
    except Exception as e:
        logger.error(f"Хато дар process_product_image: {str(e)}")
        await message.answer("Хато рух дод, лутфан дубора кӯшиш кунед! 😞")
        await state.clear()
        if 'session' in locals():
            session.close()

# Ҳазфи маҳсулот
@dp.callback_query(lambda c: c.data == "admin_delete_product")
async def admin_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастрасї ба!")
        await callback.answer()
        return

    try:
        session = Session()
        products = session.query(Product).all()
        session.close()

        if not products:
            await callback.message.answer("Ягон маҳсулот мавшуд не!")
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
        await callback.message.answer("Хато рух дод, лутфан дубора куш кунед!")
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_product_"))
async def confirm_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастрасї ба!")
        await callback.answer()
        return

    try:
        product_id = int(callback.data.split("_")[-1])
        session = Session()
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            session.close()
            await callback.message.answer("Маҳсулот ёфт нашуд!")
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Бале, ҳазф кун", callback_data=f"confirm_delete_product_{product.id}")],
            [InlineKeyboardButton(text="Не, бекор кун", callback_data="admin_delete_product")]
            ]
        )
        await callback.message.answer(
            f"Ой шумо мутмаи ҳастед , ки мехоҳед маҳсулоти '{escape_html(product.name)}'-ро хазф кунед? Ин амал ҳамаи сабадҳо ва фармоишҳои марбутараро низ хезз мекунад!",
            reply_markup="HTML", parse_mode=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар confirm_delete_product: {str(e)}")
        await callback.message.answer("Хато рух дод, лутфан дубора куш кунед!")
        await callback.answer()
        if 'session' in locals():
            session.close()

@dp.callback_query(lambda c: c.data.startswith("confirm_delete_product_"))
async def execute_delete_product(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастраси ба ин меню надоред!")
        await callback.answer()
        return

    try:
        product_id = int(callback.data.split("_")[-1])
        session = Session()
        product = session.query(Product).filter_by(id=product_id).first()

        if not product:
            session.close()
            await callback.message.answer("Маҳсулот ёфт нашуд!")
            await callback.answer()
            return

        session.query(Cart).filter_by(product_id=product.id).delete()
        session.query(Order).filter_by(id=product_id).delete()
        session.delete(product)
        session.commit()
        session.close()

        await callback.message.answer(f"Маҳсулот '{escape_html(product.name)}' <b>бомуваффақият хазф шуд!</b>", parse_mode="HTML")
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Ҳазфи маҳсулоти дигар", callback_data="admin_delete_product")],
                [InlineKeyboardButton(text="Ба панели админ", callback_data="admin_panel")]
            ]
        )
        await callback.message.answer("Амали навбат:", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар execute_delete_product: {str(e)}")
        await callback.message.answer("Хато рух дод, лутфан дубора куш кунед!")
        await callback.answer()
        if 'session' in locals():
            session.close()

# Иловаи фармоиш
@dp.callback_query(lambda c: c.data == "admin_add_order")
async def admin_add_order(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастраси ба ин меню надоред!")
        return
    try:
        session = Session()
        users = session.query(User).all()
        session.close()

        if not users:
            await callback.message.answer("Ягон корбар мавшуд!")
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"{escape_html(user.first_name)} (@{escape_html(user.username or '')})", callback_data=f"admin_select_user_{user.telegram_id}")]
                for user in users
            ]
        )
        await callback.message.answer("Корбарро интихоб кунед:", reply_markup=keyboard)
        await state.set_state(AdminOrderForm.user_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_add_order: {str(e)}")
        await callback.message.answer("Хато рух, лутфан дубора куш кун!")
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_add_order: {str(e)}")
        await callback.message.answer("Хато рух, лутфан дубора куш кун!")
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
            await callback.message.answer("Ягон маҳсулот мавшуд!")
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
        await callback.message.answer("Хато рух дод, лутфан дубора куш кунед!")
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
        await callback.message.answer("Хато рух дод, лутфан дубора куш кунед!")
        await callback.answer()

@dp.message(AdminOrderForm.quantity)
async def process_order_quantity(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Лутфан, миқдори дурустро ворид кунед (масалан, 2):")
        try:
            quantity = int(message.text)
            if quantity <= 0:
                raise ValueError("Миқдор бояд мусбат бошад!")
            data = await state.get_data()
            session = Session()
            product = session.query(Product).filter_by(id=data["product_id"]).first()
            if not product:
                await message.answer("Маҳсулот ёфт нашуд!")
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
                f"Маҳсулот: {escape_html(product.name)}, Миқдор: {quantity}, Ҳамагуй: ${product.price * quantity}",
                parse_mode="HTML"
            )
            await state.clear()
    
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Иловаи фаримоиши дигар", callback_data="admin_add_order")],
                    [InlineKeyboardButton(text="Ба панели админ", callback_data="admin_panel")]
                ]
            )
            await message.answer("Амали навбат:", reply_markup=keyboard)
    
        except Exception as e:
            logger.error(f"Хато дар process_order_quantity: {str(e)}")
            await message.answer("Лутфан, муйдори дурустро ворид кунед (масалан, 2):")
            if 'session' in locals():
                session.close()

# Намоиши рӯйхати фармоиш
@dp.callback_query(lambda c: c.data == "admin_view_orders")
async def admin_view_orders(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастраси ба ин меню надоред!")
        return
    try:
        session = Session()
        orders = session.query(Order, User, Product).join(User).join(Product).all()
        session.close()

        if not orders:
            await callback.message.answer("<b>Ягон фармоиш мавшуд!</b>", parse_mode="HTML")
            return

        response = "<b>Рӯйхати фармош:</b>\n\n"
        for order, user, product in orders:
            response += f"📦 Фармоиши навФармоиш #{order.id}\n"
            response += f"👤 Корбар: {escape_html(user.first_name)} (@{escape_html(user.username or '')})\n"
            response += f"🍫 Маҳсулотҳо: {escape_html(product.name)}\n"
            response += f"Миқми: {order.quantity}\n"
            response += f"💵 Ҳамагӣ: ${order.total}\n"
            response += f"📅 Сана: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        await callback.message.answer(response, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_view_orders: {str(e)}")
        await callback.message.answer("Хато рух, лутфан дубора кушиш кун!")
        await callback.answer()

# Идоракунии категория
@dp.callback_query(lambda c: c.data == "admin_add_category")
async def admin_add_category(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастраси ба ин меню надоред!")
        await callback.answer()
        return
    try:
        await callback.message.answer("Номи категорияро ворид кунед (масалан, Десерт):")
        await state.set_state(AdminCategoryForm.name)
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_add_category: {str(e)}")
        await callback.message.answer("Хато рух, лутфан дубора кушиш кун!")
        await callback.answer()

@dp.message(AdminCategoryForm.name)
async def process_category_name(message: types.Message, state: FSMContext):
    try:
        category_name = message.text.strip()
        if not category_name:
            await message.answer("Ном набояд холи бошад! Лутфан, номи дурусто ворид:")
            return

        session = Session()
        existing_category = session.query(Category).filter_by(name=category_name).first()
        if existing_category:
            session.close()
            await message.answer(f"Категорияи '{escape_html(category_name)}' аллакай мавшуд!")
            await state.clear()
            return

        new_category = Category(name=category_name)
        session.add(new_category)
        session.commit()
        session.close()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Эҷоди категори дигар", callback_data="admin_add_category")],
                [InlineKeyboardButton(text="Ба панели категория", callback_data="admin_manage_categories")],
                [InlineKeyboardButton(text="Ба панели админ", callback_data="admin_panel")]
            ]
        )
        await message.answer(f"<b>Категорияи '{escape_html(category_name)}'</b> бомумафафиқият эшд шуд!", reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
    except Exception as e:
        logger.error(f"Хато дар process_category_name: {str(e)}")
        await message.answer(f"Хота хангоми эдади категория: {str(e)}")
        if 'session' in locals():
            session.close()
        await state.clear()

@dp.callback_query(lambda c: c.data == "admin_delete_category")
async def admin_delete_category(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастрашї!")
        await callback.answer()
        return
    try:
        session = Session()
        categories = session.query(Category).all()
        session.close()

        if not categories:
            await callback.message.answer("Ягон категория мавшуд!")
            await callback.answer()
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=category.name, callback_data=f"delete_category_{category.id}")]
                for category in categories
            ]
        )
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Бозгаши ба идорошакини", callback_data="admin_manage_categories")])

        await callback.message.answer("<b>Категорияро барои хазф интихоб кешь:</b>", reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар admin_delete_category: {str(e)}")
        await callback.message.answer("Хато рух, лутра дубара куш!")
        await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_category_"))
async def confirm_delete_category(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.message.answer("Шумо дастрашї!")
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
                [InlineKeyboardButton(text="Хазы категори дигарши", callback_data="admin_delete_category")],
                [InlineKeyboardButton(text="Ба идорошакини", callback_data="admin_manage_categories")],
                [InlineKeyboardButton(text="Ба пана аделини", callback_data="admin_panel")]
            ]
        )
        await callback.message.answer(
            f"<b>Категорияи '{escape_html(category.name)}'</b> хаз та ва мухода ба категори пеши гозарои шуданд!",
            reply_markup=keyboard, parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Хато дар confirm_delete_category: {str(e)}")
        await callback.message.answer(f"Хато ҳангоми хазфи категория: {str(e)}")
        await callback.answer()
        if 'session' in locals():
            session.close()



@dp.message(lambda message: message.text == "🏪 Адрес")
async def addresses(message: types.Message):
    address_text = (
        "🏪 Мои пункты продаж:\n\n"
        "1. Дом печати (центр города)\n"
        "2. Ашан, 3 этаж (фудкорт)\n"
        "3. Сиёма Мол, 2 этаж\n\n"
        "🕒 График работы: 10:00-23:00"
    )
    await message.answer(address_text)

@dp.message(lambda message : message.text == "📞 Контакты")
async def contacts(message:  types.Message):
    contact_text = (
        "📱 Наши контакты:\n\n"
        "☎️ Телефон для заказов:\n"
        "+992 900-58-52-49\n"
        "+992 877-80-80-02\n\n"
        "💬 Пишите нам в любое время!"
    )
    await message.answer(contact_text)




# Оғоз
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())