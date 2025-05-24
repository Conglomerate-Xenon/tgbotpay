from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import requests
import asyncio

# === НАСТРОЙКИ ===
BOT_TOKEN = "8085507188:AAFbQP91yzQXXiGa8frag59YTtmeyvHNhrg"
TON_ADDRESS = "UQDFx5huuwaQge8xCxkjF4P80ZwvV23zphnCPwYF4XtOYkXs"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

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
                         "- 💸 В TON: /pay_ton\n"
                         "- ✨ В звёздах: /pay_stars\n"
                         "- 💼 Проверить баланс: /stars")

# === Команда /pay_ton ===
@dp.message_handler(commands=['pay_ton'])
async def pay_ton(message: types.Message):
    await message.answer(f"Отправь оплату в TON на адрес:\n`{TON_ADDRESS}`\n"
                         f"Я засчитаю оплату автоматически.",
                         parse_mode="Markdown")

# === Команда /pay_stars ===
@dp.message_handler(commands=['pay_stars'])
async def pay_stars(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"stars": 0, "ton_paid": 0}

    if users[user_id]["stars"] >= 10:
        users[user_id]["stars"] -= 10
        await message.answer("✨ Оплата звёздами прошла успешно!")
    else:
        await message.answer("Недостаточно звёзд! Нужно минимум 10 ✨")

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
            response = requests.get(url).json()
            balance = int(response["result"]) / 1e9

            if balance > last_balance:
                delta = round(balance - last_balance, 4)
                last_balance = balance

                # Рассылаем уведомление всем (или последнему активному пользователю)
                for user_id in users:
                    users[user_id]["ton_paid"] += delta
                    await bot.send_message(user_id, f"💸 Получено {delta} TON. Спасибо за оплату!")

        except Exception as e:
            print(f"[ERROR] Ошибка при проверке TON: {e}")

        await asyncio.sleep(10)

# === Обработка всех других сообщений ===
@dp.message_handler()
async def fallback(message: types.Message):
    await message.answer("Используй команды:\n/pay_ton\n/pay_stars\n/stars")

# === Запуск ===
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(check_ton_payments())
    executor.start_polling(dp, skip_updates=True)

