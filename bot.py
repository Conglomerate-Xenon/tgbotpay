import os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web
import requests
import asyncio
import logging
from aiohttp.web import Response

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "8085507188:AAFbQP91yzQXXiGa8frag59YTtmeyvHNhrg")
TON_ADDRESS = os.getenv("TON_ADDRESS", "UQDFx5huuwaQge8xCxkjF4P80ZwvV23zphnCPwYF4XtOYkXs") 
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://tgbotpay.onrender.com")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
Bot.set_current(bot)  # ВАЖНО: устанавливаем текущий бот
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Глобальные переменные
users = {}
last_balance = 0

# Обработчики команд
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"stars": 0, "ton_paid": 0}
    await message.answer("Бот работает! Команды:\n/pay_ton\n/pay_stars\n/stars\n/ping")

@dp.message_handler(commands=['ping'])
async def ping(message: types.Message):
    await message.answer("🏓 Pong! Бот активен")

@dp.message_handler(commands=['pay_ton'])
async def pay_ton(message: types.Message):
    await message.answer(
        f"Отправь оплату 0.45 TON на адрес:\n`{TON_ADDRESS}`\n"
        f"Я засчитаю оплату автоматически.",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=['pay_stars'])
async def pay_stars(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"stars": 0, "ton_paid": 0}

    if users[user_id]["stars"] >= 60:
        users[user_id]["stars"] -= 60
        await message.answer("✨ Оплата 60 звёздами прошла успешно!")
    else:
        await message.answer(
            f"Недостаточно звёзд! Нужно 60 ✨ (у вас {users[user_id]['stars']})"
        )

@dp.message_handler(commands=['stars'])
async def show_stars(message: types.Message):
    user_id = message.from_user.id
    data = users.get(user_id, {"stars": 0, "ton_paid": 0})
    await message.answer(
        f"🌟 Твои балансы:\n"
        f"- Звёзды: {data['stars']} ✨\n"
        f"- Оплачено TON: {data['ton_paid']} TON"
    )

@dp.message_handler()
async def fallback(message: types.Message):
    await message.answer("Используй команды:\n/pay_ton\n/pay_stars\n/stars\n/ping")

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
                        logger.error(f"Не удалось отправить сообщение {user_id}: {e}")

        except Exception as e:
            logger.error(f"TON CHECK ERROR: {e}")
        await asyncio.sleep(10)

# Улучшенный обработчик вебхуков
async def webhook_handler(request):
    try:
        data = await request.json()
        logger.info(f"Received update: {data}")
        
        update = types.Update(**data)
        asyncio.create_task(process_update_safely(update))
        
        return Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(text="OK")

async def process_update_safely(update: types.Update):
    try:
        await dp.process_update(update)
    except Exception as e:
        logger.error(f"Update processing failed: {e}")

# Запуск сервера
async def start_server():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    
    # Установка вебхука
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Server started on port {port}")

    # Запуск фоновой задачи
    asyncio.create_task(check_ton_payments())

    # Бесконечный цикл
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
