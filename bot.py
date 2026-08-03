import telebot
import requests
import sqlite3
import time
from telebot import types
from datetime import datetime

TOKEN = "8374531881:AAED1PSdxVQ7ebvXzHNsW5xCEzuxmgxM3lA"  # <-- вставь токен сюда
OWNER_ID = 1741201382
MANAGER_ID = 1741201382
COMMISSION = 0.38

bot = telebot.TeleBot(TOKEN)

# ================= БАЗА =================
conn = sqlite3.connect(
    "orders.db",
    check_same_thread=False,
    isolation_level=None
)

conn.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    link TEXT,
    price_cny REAL,
    total REAL,
    photo_id TEXT,
    batch_id INTEGER DEFAULT 1,
    status TEXT DEFAULT '🟡 Новый',
    date TEXT
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    created_at TEXT
)
""")
conn.execute("""
CREATE TABLE IF NOT EXISTS active_batches (
    user_id INTEGER PRIMARY KEY,
    batch_id INTEGER
)
""")
conn.execute("""
CREATE TABLE IF NOT EXISTS purchase_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    date_start TEXT,
    date_end TEXT,
    status TEXT DEFAULT '🟡 Сбор заказов',
    created_at TEXT
)
""")



conn.execute("""
CREATE TABLE IF NOT EXISTS active_purchase_group (
    id INTEGER PRIMARY KEY CHECK(id=1),
    group_id INTEGER
)
""")

try:
    conn.execute("""
    ALTER TABLE orders
    ADD COLUMN purchase_group_id INTEGER DEFAULT 0
    """)
except:
    pass

print("СТРУКТУРА ТАБЛИЦЫ ORDERS:")

print("СТРУКТУРА ТАБЛИЦЫ ORDERS:")

cursor = conn.execute("PRAGMA table_info(orders)")

for row in cursor.fetchall():
    print(row)
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
def admin_menu(message):

    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "⛔ Нет доступа")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(
            "👤 Пользователи",
            callback_data="admin_users"
        ),
        types.InlineKeyboardButton(
            "📦 Закупки",
            callback_data="admin_groups"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "📢 Рассылка",
            callback_data="admin_broadcast"
        ),
        types.InlineKeyboardButton(
            "📊 Статистика",
            callback_data="admin_stats"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "⚙ Настройки",
            callback_data="admin_settings"
        )
    )

    bot.send_message(
        message.chat.id,
        "⚙ Панель администратора",
        reply_markup=markup
    )

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
        admin_menu(message)

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
            f"💰 Итого: {total:.2f} BYN, без учета доставки.",
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
        bot.send_message(message.chat.id, "↩ Вы в меню", reply_markup=main_menu())
        return

    if message.content_type != "photo":
        msg = bot.send_message(message.chat.id, "❌ Нужна фотография", reply_markup=back_markup())
        bot.register_next_step_handler(msg, get_photo)
        return

    data = user_data.get(message.chat.id)
    if not data:
        bot.send_message(message.chat.id, "Ошибка данных", reply_markup=main_menu())
        return

    photo_id = message.photo[-1].file_id
    username = message.from_user.username or "no_username"

    batch = conn.execute(
        """
        SELECT batch_id
        FROM active_batches
        WHERE user_id = ?
        """,
        (message.from_user.id,)
    ).fetchone()

    if batch:
        batch_id = batch[0]
    else:
        conn.execute("""
            INSERT INTO batches(user_id, created_at)
            VALUES(?, ?)
        """, (
            message.from_user.id,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

        batch_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        conn.execute("""
            INSERT OR REPLACE INTO active_batches(user_id, batch_id)
            VALUES(?, ?)
        """, (
            message.from_user.id,
            batch_id
        ))

    group = conn.execute("""
    SELECT group_id
    FROM active_purchase_group
    WHERE id=1
    """).fetchone()

    purchase_group = 0

    if group:
        purchase_group = group[0]



    conn.execute("""
    INSERT INTO orders (
        user_id,
        username,
        link,
        price_cny,
        total,
        photo_id,
        batch_id,
        purchase_group_id,
        status,
        date
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        username,
        data["link"],
        data["price"],
        data["total"],
        photo_id,
        batch_id,
        purchase_group,
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
        caption=
        f"📦 Заказ №{last_id}\n\n"
        f"👤 @{username}\n"
        f"🔗 {data['link']}\n"
        f"💰 {data['total']:.2f} BYN\n\n"
        f"Статус: 🟡 Новый",
        reply_markup=markup
    )

    reset_user(message.chat.id)


# ================= МОИ ЗАКАЗЫ =================
def show_my_orders(message):

    cursor = conn.execute("""
        SELECT
            batch_id,
            COUNT(*),
            SUM(total),
            MIN(status)
        FROM orders
        WHERE user_id = ?
        GROUP BY batch_id
        ORDER BY batch_id DESC
    """, (message.from_user.id,))

    batches = cursor.fetchall()

    if not batches:
        bot.send_message(message.chat.id, "📭 Нет заказов")
        return

    for batch_id, count_orders, total_sum, status in batches:

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "📂 Открыть список",
                callback_data=f"userbatch_{batch_id}"
            )
        )

        bot.send_message(
            message.chat.id,
            f"📦 Список №{batch_id}\n"
            f"📦 Товаров: {count_orders}\n"
            f"💰 Сумма: {total_sum:.2f} BYN\n"
            f"📌 Статус: {status}",
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
        markup.row(
            types.InlineKeyboardButton(
                f"👤 @{username}",
                callback_data=f"user_{user_id}"
            ),
            types.InlineKeyboardButton(
                "➕ Новый список",
                callback_data=f"newbatch_{user_id}"
            )
        )

    bot.send_message(
        message.chat.id,
        "📱 Выберите пользователя:",
        reply_markup=markup
    )

# ================= ФИЛЬТР =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("user_"))
def user_report(call):
    if call.from_user.id != OWNER_ID:
        return

    user_id = call.data.split("_")[1]

    cursor = conn.execute("""
        SELECT
            batch_id,
            COUNT(*),
            SUM(total),
            MIN(status)
        FROM orders
        WHERE user_id = ?
        GROUP BY batch_id
        ORDER BY batch_id DESC
    """, (user_id,))

    orders = cursor.fetchall()

    if not orders:
        bot.send_message(call.message.chat.id, "📭 Нет заказов")
        return

    total_sum = 0
    bot.send_message(call.message.chat.id, f"👤 Заказы пользователя {user_id}")

    for batch_id, count_orders, total_sum_batch, status in orders:
        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "📂 Открыть",
                callback_data=f"batch_{batch_id}"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "✏ Изменить статус",
                callback_data=f"batchstatus_{batch_id}"
            )
        )

        bot.send_message(
            call.message.chat.id,
            f"📦 Партия №{batch_id}\n"
            f"📦 Товаров: {count_orders}\n"
            f"💰 Сумма: {total_sum_batch:.2f} BYN\n"
            f"📌 Статус: {status}",
            reply_markup=markup
        )



    bot.send_message(call.message.chat.id, f"💰 Сумма: {total_sum:.2f} BYN")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("newbatch_"))
def create_new_batch(call):

    if call.from_user.id != OWNER_ID:
        return

    user_id = int(call.data.split("_")[1])

    conn.execute("""
        INSERT INTO batches(user_id, created_at)
        VALUES(?, ?)
    """, (
        user_id,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))

    batch_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.execute("""
        INSERT OR REPLACE INTO active_batches(user_id, batch_id)
        VALUES(?, ?)
    """, (
        user_id,
        batch_id
    ))

    bot.answer_callback_query(
        call.id,
        f"Создан список №{batch_id}"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("batch_"))
def open_batch(call):

    batch_id = call.data.split("_")[1]

    cursor = conn.execute("""
        SELECT id, link, price_cny, total, photo_id, status, date
        FROM orders
        WHERE batch_id = ?
    """, (batch_id,))

    orders = cursor.fetchall()

    for order in orders:

        order_id, link, price_cny, total, photo_id, status, date = order

        bot.send_photo(
            call.message.chat.id,
            photo_id,
            caption=
            f"📦 #{order_id}\n"
            f"🔗 {link}\n"
            f"💴 {price_cny} CNY\n"
            f"💰 {total:.2f} BYN\n"
            f"📌 {status}\n"
            f"📅 {date}"
        )

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
                f"📦 Заказ №{order_id}\n\n"
                f"Новый статус:\n{status}"
            )
        except:
            pass

    bot.answer_callback_query(
        call.id,
        f"Статус изменён: {status}"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def delete_order(call):
    order_id = int(call.data.split("_")[1])

    conn.execute(
        "DELETE FROM orders WHERE id=? AND user_id=?",
        (order_id, call.from_user.id)
    )

    bot.answer_callback_query(call.id, "✅ Заказ удалён")

    try:
        bot.delete_message(
            call.message.chat.id,
            call.message.message_id
        )
    except:
        pass

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("batchstatus_")
)
def batch_status_menu(call):

    batch_id = call.data.split("_")[1]

    markup = types.InlineKeyboardMarkup()

    markup.row(
        types.InlineKeyboardButton(
            "🟡 Новый",
            callback_data=f"setbatch_new_{batch_id}"
        ),
        types.InlineKeyboardButton(
            "🔵 В работе",
            callback_data=f"setbatch_work_{batch_id}"
        )
    )

    markup.row(
        types.InlineKeyboardButton(
            "🟢 Оплачен",
            callback_data=f"setbatch_paid_{batch_id}"
        ),
        types.InlineKeyboardButton(
            "✅ Получен",
            callback_data=f"setbatch_done_{batch_id}"
        )
    )


    bot.send_message(
        call.message.chat.id,
        f"Выберите статус для партии №{batch_id}",
        reply_markup=markup
    )

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("setbatch_")
)
def set_batch_status(call):

    _, status_code, batch_id = call.data.split("_")

    statuses = {
        "new": "🟡 Новый",
        "work": "🔵 В работе",
        "paid": "🟢 Оплачен",
        "done": "✅ Получен"
    }

    status = statuses[status_code]

    conn.execute("""
        UPDATE orders
        SET status = ?
        WHERE batch_id = ?
    """, (status, batch_id))

    cursor = conn.execute("""
        SELECT DISTINCT user_id
        FROM orders
        WHERE batch_id = ?
    """, (batch_id,))

    users = cursor.fetchall()

    for user in users:
        try:
            bot.send_message(
                user[0],
                f"📦 Ваш список №{batch_id}\n\n"
                f"Новый статус:\n{status}"
            )
        except Exception as e:
            print(e)

    bot.answer_callback_query(
        call.id,
        f"Партия №{batch_id}: {status}"
    )
@bot.callback_query_handler(func=lambda call: call.data.startswith("userbatch_"))
def open_user_batch(call):

    batch_id = call.data.split("_")[1]

    cursor = conn.execute("""
        SELECT id, link, price_cny, total,
               photo_id, status, date
        FROM orders
        WHERE batch_id = ?
        ORDER BY id DESC
    """, (batch_id,))

    orders = cursor.fetchall()

    for order in orders:
        order_id, link, price_cny, total, photo_id, status, date = order

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "🗑 Удалить заказ",
                callback_data=f"del_{order_id}"
            )
        )

        bot.send_photo(
            call.message.chat.id,
            photo_id,
            caption=
            f"📦 #{order_id}\n"
            f"🔗 {link}\n"
            f"💴 {price_cny} CNY\n"
            f"💰 {total:.2f} BYN\n"
            f"📌 {status}\n"
            f"📅 {date}",
            reply_markup=markup
        )

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("grouporders_"))
def group_orders(call):

    group_id = int(call.data.split("_")[1])

    cursor = conn.execute("""
        SELECT
            id,
            username,
            total
        FROM orders
        WHERE purchase_group_id=?
        ORDER BY id DESC
    """, (group_id,))

    orders = cursor.fetchall()

    if not orders:

        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            "📭 В этой закупке нет заказов."
        )

        return

    markup = types.InlineKeyboardMarkup()

    for order_id, username, total in orders:

        markup.add(
            types.InlineKeyboardButton(
                f"📦 #{order_id} | @{username} | {total:.2f} BYN",
                callback_data=f"grouporder_{order_id}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        "📦 Все товары закупки",
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("grouporder_"))
def open_group_order(call):

    order_id = int(call.data.split("_")[1])

    order = conn.execute("""
        SELECT
            username,
            link,
            price_cny,
            total,
            photo_id,
            status,
            date
        FROM orders
        WHERE id=?
    """, (order_id,)).fetchone()

    if not order:

        bot.answer_callback_query(call.id)

        return

    username, link, price_cny, total, photo_id, status, date = order

    bot.send_photo(
        call.message.chat.id,
        photo_id,
        caption=
        f"📦 Заказ №{order_id}\n\n"
        f"👤 @{username}\n\n"
        f"🔗 {link}\n\n"
        f"💴 {price_cny} CNY\n"
        f"💰 {total:.2f} BYN\n\n"
        f"📌 {status}\n"
        f"📅 {date}"
    )

    bot.answer_callback_query(call.id)

# ================= RUN =================
import time

@bot.callback_query_handler(func=lambda call: call.data == "admin_groups")
def admin_groups(call):

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "➕ Создать закупку",
            callback_data="create_group"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "📂 Открыть закупки",
            callback_data="open_groups"
        )
    )

    bot.edit_message_text(
        "📦 Управление закупками",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "create_group")
def create_group(call):

    bot.answer_callback_query(call.id)

    msg = bot.send_message(
        call.message.chat.id,
        "📅 Введите дату начала закупки\n\nНапример:\n20.07.2026"
    )

    bot.register_next_step_handler(msg, get_group_start_date)

def get_group_start_date(message):

    user_data[message.chat.id] = {
        "group_start": message.text
    }

    msg = bot.send_message(
        message.chat.id,
        "📅 Введите дату окончания закупки\n\nНапример:\n25.07.2026"
    )

    bot.register_next_step_handler(msg, get_group_end_date)

def get_group_end_date(message):

    start = user_data[message.chat.id]["group_start"]
    end = message.text

    title = f"{start} - {end}"

    conn.execute("""
        INSERT INTO purchase_groups(
            title,
            date_start,
            date_end,
            created_at
        )
        VALUES(?,?,?,?)
    """, (
        title,
        start,
        end,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))

    group_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.execute("""
        INSERT OR REPLACE INTO active_purchase_group(id, group_id)
        VALUES(1, ?)
    """, (group_id,))

    bot.send_message(
        message.chat.id,
        f"✅ Закупка создана\n\n📦 {title}"
    )

    user_data.pop(message.chat.id, None)
@bot.callback_query_handler(func=lambda call: call.data == "open_groups")
def open_groups(call):

    cursor = conn.execute("""
        SELECT id, title, status
        FROM purchase_groups
        ORDER BY id DESC
    """)

    groups = cursor.fetchall()

    if not groups:
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📭 Закупок пока нет."
        )
        return

    markup = types.InlineKeyboardMarkup()

    for group_id, title, status in groups:

        markup.add(
            types.InlineKeyboardButton(
                f"📦 {title} | {status}",
                callback_data=f"group_{group_id}"
            )
        )

    bot.edit_message_text(
        "📂 Список закупок",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("group_"))
def open_group(call):

    group_id = int(call.data.split("_")[1])

    group = conn.execute("""
        SELECT
            title,
            status
        FROM purchase_groups
        WHERE id=?
    """, (group_id,)).fetchone()

    if not group:
        bot.answer_callback_query(call.id, "Не найдено")
        return

    title, status = group

    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(
            "👥 Клиенты",
            callback_data=f"groupusers_{group_id}"
        ),
        types.InlineKeyboardButton(
            "📦 Заказы",
            callback_data=f"grouporders_{group_id}"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "📢 Рассылка",
            callback_data=f"groupbroadcast_{group_id}"
        ),
        types.InlineKeyboardButton(
            "📊 Статистика",
            callback_data=f"groupstat_{group_id}"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "✏ Изменить статус",
            callback_data=f"groupstatus_{group_id}"
        )
    )

    bot.edit_message_text(
        f"📦 Закупка\n\n"
        f"📅 {title}\n"
        f"📌 {status}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("groupusers_"))
def group_users(call):

    group_id = int(call.data.split("_")[1])

    cursor = conn.execute("""
        SELECT
            user_id,
            username,
            COUNT(*),
            SUM(total)
        FROM orders
        WHERE purchase_group_id=?
        GROUP BY user_id
        ORDER BY username
    """, (group_id,))

    users = cursor.fetchall()

    if not users:
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📭 В этой закупке пока нет заказов."
        )
        return

    markup = types.InlineKeyboardMarkup()

    for user_id, username, count_orders, total_sum in users:

        text = f"👤 @{username} | {count_orders} тов. | {total_sum:.2f} BYN"

        markup.add(
            types.InlineKeyboardButton(
                text,
                callback_data=f"groupuser_{group_id}_{user_id}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        "👥 Участники закупки:",
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("groupbroadcast_"))
def group_broadcast(call):

    group_id = int(call.data.split("_")[1])

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "📦 Заказы выкуплены",
            callback_data=f"sendgroup_{group_id}_buy"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🚛 Машина выехала",
            callback_data=f"sendgroup_{group_id}_truck"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "✈ Груз в пути",
            callback_data=f"sendgroup_{group_id}_way"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🏢 Прибыл в Беларусь",
            callback_data=f"sendgroup_{group_id}_belarus"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "📦 Разбираем склад",
            callback_data=f"sendgroup_{group_id}_warehouse"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "✅ Можно забирать",
            callback_data=f"sendgroup_{group_id}_ready"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "✍ Свое сообщение",
            callback_data=f"customgroup_{group_id}"
        )
    )

    bot.edit_message_text(
        "📢 Выберите сообщение",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sendgroup_"))
def send_group_message(call):

    _, group_id, code = call.data.split("_")

    texts = {
        "buy":
        "📦 Ваши товары успешно выкуплены.\n\nСледующий этап — отправка в Беларусь.",

        "truck":
        "🚛 Машина с вашим грузом выехала из Китая.",

        "way":
        "✈ Ваш груз находится в пути.",

        "belarus":
        "🏢 Ваш груз прибыл в Беларусь.",

        "warehouse":
        "📦 Сейчас происходит разбор груза на складе.",

        "ready":
        "✅ Ваш заказ готов к выдаче."
    }

    text = texts[code]

    cursor = conn.execute("""
        SELECT DISTINCT user_id
        FROM orders
        WHERE purchase_group_id=?
    """, (group_id,))

    users = cursor.fetchall()

    count = 0

    for user in users:

        try:

            bot.send_message(
                user[0],
                text
            )

            count += 1

        except:
            pass

    bot.answer_callback_query(
        call.id,
        f"Отправлено: {count}"
    )





@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def open_admin_users(call):

    class FakeMessage:
        pass

    fake = FakeMessage()
    fake.chat = call.message.chat
    fake.from_user = call.from_user

    show_admin_report(fake)

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("groupstatus_"))
def change_group_status(call):

    group_id = int(call.data.split("_")[1])

    markup = types.InlineKeyboardMarkup(row_width=2)

    statuses = [
        "🟡 Сбор заказов",
        "🟢 Заказы выкуплены",
        "🚛 Машина выехала",
        "✈ Груз в пути",
        "🏢 Прибыл в Беларусь",
        "📦 Разбираем склад",
        "✅ Готов к выдаче",
        "🔴 Закупка закрыта"
    ]

    for i, status in enumerate(statuses):
        markup.add(
            types.InlineKeyboardButton(
                status,
                callback_data=f"setgroupstatus_{group_id}_{i}"
            )
        )

    bot.edit_message_text(
        "✏ Выберите новый статус:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("setgroupstatus_"))
def set_group_status(call):

    parts = call.data.split("_")

    group_id = int(parts[1])
    status_index = int(parts[2])

    statuses = [
        "🟡 Сбор заказов",
        "🟢 Заказы выкуплены",
        "🚛 Машина выехала",
        "✈ Груз в пути",
        "🏢 Прибыл в Беларусь",
        "📦 Разбираем склад",
        "✅ Готов к выдаче",
        "🔴 Закупка закрыта"
    ]

    new_status = statuses[status_index]

    conn.execute("""
        UPDATE purchase_groups
        SET status=?
        WHERE id=?
    """, (new_status, group_id))

    bot.answer_callback_query(
        call.id,
        "✅ Статус изменён"
    )

    # Открываем карточку закупки заново
    class FakeCall:
        pass

    fake = FakeCall()
    fake.data = f"group_{group_id}"
    fake.message = call.message
    fake.id = call.id

    open_group(fake)

print("Бот запущен...")

bot.remove_webhook()

while True:
    try:
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60
        )
    except Exception as e:
        print("Ошибка:", e)
        time.sleep(10)
