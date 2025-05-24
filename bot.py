import os
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.webhook import SendMessage
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web
import requests
import asyncio

# === НАСТРОЙКИ ===
BOT_ON_RENDER = "RENDER" not in os.environ  # Проверка, запущен ли код на Render
BOT_TOKEN = "8085507188:AAFbQP91yzQXXiGa8frag59YTtmeyvHNhrg"
TON_ADDRESS = "UQDFx5huuwaQge8xCxkjF4P80ZwvV23zphnCPwYF4XtOYkXs"
WEBHOOK_HOST = "https://tgbotpay.onrender.com"  # Ваш URL на Render
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Словари
users = {}         # user_id: {"stars": int, "ton_paid": float}
last_balance = 0   # Предыдущий баланс TON

# === Команда /start ===
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"stars": 0, "ton_paid": 0}
    await message.answer("Привет! Ты можешь оплатить:\n"
                         "- 💸 0.45 TON: /pay_ton\n"
                         "- ✨ 60 звёзд: /pay_stars\n"
                         "- 💼 Проверить баланс: /stars")

# === Команда /pay_ton ===
@dp.message_handler(commands=['pay_ton'])
async def pay_ton(message: types.Message):
    await message.answer(f"Отправь оплату 0.45 TON на адрес:\n`{TON_ADDRESS}`\n"
                         f"Я засчитаю оплату автоматически.",
                         parse_mode="Markdown")

# === Команда /pay_stars ===
@dp.message_handler(commands=['pay_stars'])
async def pay_stars(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"stars": 0, "ton_paid": 0}

    if users[user_id]["stars"] >= 60:
        users[user_id]["stars"] -= 60
        await message.answer("✨ Оплата 60 звёздами прошла успешно!")
    else:
        await message.answer(f"Недостаточно звёзд! Нужно 60 ✨ (у вас {users[user_id]['stars']})")

# === Команда /stars ===
@dp.message_handler(commands=['stars'])
async def show_stars(message: types.Message):
    user_id = message.from_user.id
    data = users.get(user_id, {"stars": 0, "ton_paid": 0})
    await message.answer(f"🌟 Твои балансы:\n"
                         f"- Звёзды: {data['stars']} ✨\n"
                         f"- Оплачено TON: {data['ton_paid']} TON")

# === Фоновая задача: отслеживание TON ===
async def check_ton_payments():
    global last_balance
    while True:
        try:
            url = f"https://toncenter.com/api/v2/getAddressBalance?address={TON_ADDRESS}"
            response = requests.get(url, timeout=5).json()
            balance = int(response["result"]) / 1e9

            if balance > last_balance:
                delta = round(balance - last_balance, 4)
                last_balance = balance

                for user_id in users:
                    users[user_id]["ton_paid"] += delta
                    try:
                        await bot.send_message(user_id, f"💸 Получено {delta} TON. Спасибо за оплату!")
                    except Exception as e:
                        print(f"[ERROR] Не удалось отправить сообщение {user_id}: {e}")

        except Exception as e:
            print(f"[TON CHECK ERROR] {e}")
        await asyncio.sleep(10)

# === Обработка всех других сообщений ===
@dp.message_handler()
async def fallback(message: types.Message):
    await message.answer("Используй команды:\n/pay_ton\n/pay_stars\n/stars")

# === Настройка вебхуков ===
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(check_ton_payments())  # Запуск фоновой задачи

async def on_shutdown(app):
    await bot.delete_webhook()

# === Запуск сервера ===
if __name__ == "__main__":
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, dp._check_webhook)  # Обработчик вебхуков
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Запуск на Render (порт берется из переменной окружения)
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

