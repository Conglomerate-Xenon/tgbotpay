import os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web
import requests
import asyncio
import logging
from aiohttp.web import Response

# === Настройка логов ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === Конфигурация ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8085507188:AAFbQP91yzQXXiGa8frag59YTtmeyvHNhrg")
TON_ADDRESS = "UQDFx5huuwaQge8xCxkjF4P80ZwvV23zphnCPwYF4XtOYkXs"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://tgbotpay.onrender.com")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# === Инициализация бота ===
bot = Bot(token=BOT_TOKEN)
Bot.set_current(bot)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Словари
users = {}
last_balance = 0

# === Обработчики команд ===
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    try:
        user_id = message.from_user.id
        if user_id not in users:
            users[user_id] = {"stars": 0, "ton_paid": 0}
        
        logger.info(f"Processing /start for user {user_id}")
        await message.answer("Привет! Вот доступные команды:\n"
                           "/pay_ton - Оплата TON\n"
                           "/pay_stars - Оплата звёздами\n"
                           "/stars - Баланс\n"
                           "/ping - Проверка связи")
    except Exception as e:
        logger.error(f"Error in start handler: {e}")

@dp.message_handler(commands=['ping'])
async def ping(message: types.Message):
    try:
        logger.info(f"Ping from {message.from_user.id}")
        await message.answer("🏓 Pong! Бот активен")
    except Exception as e:
        logger.error(f"Ping error: {e}")

@dp.message_handler(commands=['pay_ton'])
async def pay_ton(message: types.Message):
    await message.answer(f"Отправь оплату 0.45 TON на адрес:\n`{TON_ADDRESS}`\n"
                        f"Я засчитаю оплату автоматически.",
                        parse_mode="Markdown")

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

@dp.message_handler(commands=['stars'])
async def show_stars(message: types.Message):
    user_id = message.from_user.id
    data = users.get(user_id, {"stars": 0, "ton_paid": 0})
    await message.answer(f"🌟 Твои балансы:\n"
                        f"- Звёзды: {data['stars']} ✨\n"
                        f"- Оплачено TON: {data['ton_paid']} TON")

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

# === Улучшенный обработчик вебхуков ===
async def webhook_handler(request):
    try:
        data = await request.json()
        logger.info(f"Incoming update: {data}")
        
        # Быстрая проверка валидности данных
        if not data.get('update_id'):
            logger.warning("Invalid update received")
            return Response(text="OK")
            
        update = types.Update(**data)
        
        # Обработка в отдельной задаче
        asyncio.create_task(safe_process_update(update))
        
        return Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        return Response(text="OK")

async def safe_process_update(update: types.Update):
    try:
        await dp.process_update(update)
    except Exception as e:
        logger.error(f"Update processing error: {e}")

# === Запуск сервера ===
async def on_startup(app):
    try:
        await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)
        logger.info("Webhook set successfully")
        
        # Запуск фоновых задач
        asyncio.create_task(check_ton_payments())
    except Exception as e:
        logger.error(f"Startup error: {e}")

async def on_shutdown(app):
    try:
        await bot.delete_webhook()
        await dp.storage.close()
        await dp.storage.wait_closed()
        logger.info("Bot shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Установка лимитов для aiohttp
    runner = web.AppRunner(app, handle_signals=True)
    return runner

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    runner = main()
    
    async def start_app():
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"Server started on port {port}")
        
        # Бесконечное ожидание
        while True:
            await asyncio.sleep(3600)
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_app())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(runner.cleanup())
        loop.close()
