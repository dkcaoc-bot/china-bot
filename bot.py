import telebot
import requests
import sqlite3
from telebot import types
from datetime import datetime

TOKEN = "8374531881:AAED1PSdxVQ7ebvXzHNsW5xCEzuxmgxM3lA"  # <-- вставь токен сюда
OWNER_ID = 1741201382
MANAGER_ID = 1741201382
COMMISSION = 0.38

bot = telebot.TeleBot(TOKEN)

# ================= БАЗА =================
conn = sqlite3.connect("orders.db", check_same_thread=False, isolation_level=None)
conn.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    link TEXT,
    price_cny REAL,
    total REAL,
    photo_id TEXT,
    status TEXT DEFAULT '🟡 Новый',
    date TEXT
)
""")

# ================= ДАННЫЕ =================
user_data = {}


# ================= КУРС =================
def get_cny_to_byn():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/CNY"
        data = requests.get(url, timeout=10).json()
        return data["rates"]["BYN"]
    except:
        return 0.45


# ================= МЕНЮ =================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        "🧮 Рассчитать стоимость",
        "📦 Новый заказ",
        "📋 Мои заказы",
        "📱 Отчёт для телефона",
        "ℹ Помощь"
    )
    return markup


def back_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("⬅ Назад")
    return markup


def reset_user(user_id):
    user_data.pop(user_id, None)
    bot.clear_step_handler_by_chat_id(user_id)


# ================= START =================
@bot.message_handler(commands=['start'])
def start(message):
    reset_user(message.chat.id)
    bot.send_message(message.chat.id, "👋 Добро пожаловать!", reply_markup=main_menu())


# ================= МЕНЮ =================
@bot.message_handler(func=lambda m: True)
def menu_handler(message):
    if message.text == "⬅ Назад":
        reset_user(message.chat.id)
        bot.send_message(message.chat.id, "↩ Вы в меню", reply_markup=main_menu())
        return

    elif message.text == "🧮 Рассчитать стоимость":
        msg = bot.send_message(message.chat.id, "Введите цену в CNY:", reply_markup=back_markup())
        bot.register_next_step_handler(msg, calculate)

    elif message.text == "📦 Новый заказ":
        msg = bot.send_message(message.chat.id, "🔗 Отправьте ссылку:", reply_markup=back_markup())
        bot.register_next_step_handler(msg, get_link)

    elif message.text == "📋 Мои заказы":
        show_my_orders(message)

    elif message.text == "📱 Отчёт для телефона":
        show_admin_report(message)

    elif message.text == "ℹ Помощь":
        bot.send_message(message.chat.id, "Бот для заказов.", reply_markup=main_menu())

    else:
        bot.send_message(message.chat.id, "Выберите кнопку 👇", reply_markup=main_menu())


# ================= РАСЧЁТ =================
def calculate(message):
    if message.text == "⬅ Назад":
        reset_user(message.chat.id)
        bot.send_message(message.chat.id, "↩ Вы в меню", reply_markup=main_menu())
        return

    try:
        price = float(message.text.replace(",", "."))
        total = price * get_cny_to_byn() * (1 + COMMISSION)

        bot.send_message(
            message.chat.id,
            f"💰 Итого: {total:.2f} BYN",
            reply_markup=main_menu()
        )

    except:
        msg = bot.send_message(message.chat.id, "❌ Введите число", reply_markup=back_markup())
        bot.register_next_step_handler(msg, calculate)


# ================= НОВЫЙ ЗАКАЗ =================
def get_link(message):
    if message.text == "⬅ Назад":
        reset_user(message.chat.id)
        bot.send_message(message.chat.id, "↩ Вы в меню", reply_markup=main_menu())
        return

    user_data[message.chat.id] = {"link": message.text}

    msg = bot.send_message(message.chat.id, "💴 Цена в CNY:", reply_markup=back_markup())
    bot.register_next_step_handler(msg, get_price)


def get_price(message):
    if message.text == "⬅ Назад":
        reset_user(message.chat.id)
        bot.send_message(message.chat.id, "↩ Вы в меню", reply_markup=main_menu())
        return

    try:
        price = float(message.text.replace(",", "."))
        total = price * get_cny_to_byn() * (1 + COMMISSION)

        user_data[message.chat.id].update({
            "price": price,
            "total": total
        })

        msg = bot.send_message(message.chat.id, "📸 Отправьте фото:", reply_markup=back_markup())
        bot.register_next_step_handler(msg, get_photo)

    except:
        msg = bot.send_message(message.chat.id, "❌ Введите число", reply_markup=back_markup())
        bot.register_next_step_handler(msg, get_price)


def get_photo(message):
    if message.text == "⬅ Назад":
        reset_user(message.chat.id)
        bot.send_message(
            message.chat.id,
            "↩ Вы в меню",
            reply_markup=main_menu()
        )
        return

    if message.content_type != "photo":
        msg = bot.send_message(
            message.chat.id,
            "❌ Нужна фотография",
            reply_markup=back_markup()
        )
        bot.register_next_step_handler(msg, get_photo)
        return

    data = user_data.get(message.chat.id)

    if not data:
        bot.send_message(
            message.chat.id,
            "Ошибка данных",
            reply_markup=main_menu()
        )
        return

    photo_id = message.photo[-1].file_id
    username = message.from_user.username or "no_username"

    conn.execute("""
    INSERT INTO orders
    (user_id, username, link, price_cny, total, photo_id, status, date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        username,
        data["link"],
        data["price"],
        data["total"],
        photo_id,
        "🟡 Новый",
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))

    last_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    bot.send_message(
        message.chat.id,
        "✅ Заказ сохранён!",
        reply_markup=main_menu()
    )

    markup = types.InlineKeyboardMarkup()

    markup.row(
        types.InlineKeyboardButton(
            "🟡 Новый",
            callback_data=f"status_new_{last_id}"
        ),
        types.InlineKeyboardButton(
            "🔵 В работе",
            callback_data=f"status_work_{last_id}"
        )
    )

    markup.row(
        types.InlineKeyboardButton(
            "🟢 Оплачен",
            callback_data=f"status_paid_{last_id}"
        ),
        types.InlineKeyboardButton(
            "✅ Получен",
            callback_data=f"status_done_{last_id}"
        )
    )

    bot.send_photo(
        MANAGER_ID,
        photo_id,
        caption=(
            f"📦 Заказ №{last_id}\n\n"
            f"👤 @{username}\n"
            f"🔗 {data['link']}\n"
            f"💰 {data['total']:.2f} BYN\n\n"
            f"📌 Статус: 🟡 Новый"
        ),
        reply_markup=markup
    )

    reset_user(message.chat.id)


# ================= МОИ ЗАКАЗЫ =================
def show_my_orders(message):
    cursor = conn.execute("""
        SELECT id, link, price_cny, total, photo_id, status, date
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
    """, (message.from_user.id,))

    orders = cursor.fetchall()

    if not orders:
        bot.send_message(message.chat.id, "📭 Нет заказов")
        return


    total_sum = 0
    bot.send_message(message.chat.id, f"📋 Заказов: {len(orders)}")

    for order in orders:
        order_id, link, price_cny, total, photo_id, status, date = order
        total_sum += total

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"del_{order_id}"))

    bot.send_photo(
        message.chat.id,
        photo_id,
        caption=(
            f"🆕 Новый заказ\n\n"
            f"📦 №{last_id}\n\n"
            f"👤 @{username}\n"
            f"🔗 {data['link']}\n"
            f"💰 {data['total']:.2f} BYN\n\n"
            f"Статус:\n"
            f"🟡 Новый"
        ),
        reply_markup=markup
    )

    bot.send_message(message.chat.id, f"💰 Сумма: {total_sum:.2f} BYN")


# ================= УДАЛЕНИЕ =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def delete_order(call):
    order_id = call.data.split("_")[1]
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    bot.answer_callback_query(call.id, "Удалено")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)


# ================= АДМИН ОТЧЁТ =================
def show_admin_report(message):
    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "⛔ Нет доступа")
        return

    cursor = conn.execute("""
        SELECT user_id, username
        FROM orders
        GROUP BY user_id
    """)

    users = cursor.fetchall()

    if not users:
        bot.send_message(message.chat.id, "📭 Нет заказов")
        return

    markup = types.InlineKeyboardMarkup()

    for user_id, username in users:
        markup.add(types.InlineKeyboardButton(
            f"👤 @{username} ({user_id})",
            callback_data=f"user_{user_id}"
        ))

    bot.send_message(message.chat.id, "📱 Выберите пользователя:", reply_markup=markup)


# ================= ФИЛЬТР =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("user_"))
def user_report(call):
    if call.from_user.id != OWNER_ID:
        return

    user_id = call.data.split("_")[1]

    cursor = conn.execute("""
        SELECT id, link, price_cny, total, photo_id, status, date
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))

    orders = cursor.fetchall()

    if not orders:
        bot.send_message(call.message.chat.id, "📭 Нет заказов")
        return

    total_sum = 0
    bot.send_message(call.message.chat.id, f"👤 Заказы пользователя {user_id}")

    for order in orders:
        order_id, username, link, price_cny, total, photo_id, date = order
        total_sum += total

        bot.send_photo(
            call.message.chat.id,
            photo_id,
            caption=f"📦 #{order_id}\n🔗 {link}\n💴 {price_cny} CNY\n💰 {total:.2f} BYN\n📅 {date}"
        )

    bot.send_message(call.message.chat.id, f"💰 Сумма: {total_sum:.2f} BYN")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("status_")
)
def change_status(call):
    if call.from_user.id != OWNER_ID:
        return

    _, status_code, order_id = call.data.split("_")

    statuses = {
        "new": "🟡 Новый",
        "work": "🔵 В работе",
        "paid": "🟢 Оплачен",
        "done": "✅ Получен"
    }

    status = statuses[status_code]

    conn.execute(
        "UPDATE orders SET status=? WHERE id=?",
        (status, order_id)
    )

    user = conn.execute(
        "SELECT user_id FROM orders WHERE id=?",
        (order_id,)
    ).fetchone()

    if user:
        try:
            bot.send_message(
                user[0],
                f"📦 Заказ №{order_id}\n\nСтатус изменён:\n\n{status}"
            )
        except:
            pass

    bot.answer_callback_query(
        call.id,
        f"Статус изменён: {status}"
    )


# ================= RUN =================
import time

while True:
    try:
        print("Бот запущен...")

        bot.polling(
            none_stop=True,
            interval=2,
            timeout=60,
            long_polling_timeout=60
        )

    except Exception as e:
        print(f"Ошибка: {e}")
        print("Перезапуск через 10 секунд...")
        time.sleep(10)
