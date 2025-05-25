import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web, ClientSession
from aiohttp.web import Response
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()

# Получение переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
TON_ADDRESS = os.getenv("TON_ADDRESS")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", 10000))

# Проверка, если токен не найден
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден. Убедитесь, что он задан в .env или через Render Environment.")

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Глобальные переменные
users = {}
last_balance = 0

# Команды
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in users:
        users[user_id] = {"stars": 0, "ton_paid": 0}
    await message.answer(
        "🤖 <b>Бот активен!</b>\n\n"
        "✨ <b>Команды:</b>\n"
        "💵 /pay_ton – оплатить в TON\n"
        "🌟 /pay_stars – оплатить звёздами\n"
        "📊 /stars – показать баланс\n"
        "🏓 /ping – проверить работу бота",
        parse_mode="HTML"
    )

@dp.message_handler(commands=['ping'])
async def ping(message: types.Message):
    await message.answer("🏓 Pong! Бот на связи!")

@dp.message_handler(commands=['pay_ton'])
async def pay_ton(message: types.Message):
    await message.answer(
        f"💳 Отправь <b>0.45 TON</b> на адрес:\n<code>{TON_ADDRESS}</code>\n"
        f"Я засчитаю оплату автоматически 💸",
        parse_mode="HTML"
    )

@dp.message_handler(commands=['pay_stars'])
async def pay_stars(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in users:
        users[user_id] = {"stars": 0, "ton_paid": 0}

    if users[user_id]["stars"] >= 60:
        users[user_id]["stars"] -= 60
        await message.answer("🌟 Оплата 60 звёздами прошла успешно! Спасибо!")
    else:
        await message.answer(
            f"❌ Недостаточно звёзд! Нужно 60 ✨ (у тебя {users[user_id]['stars']})"
        )

@dp.message_handler(commands=['stars'])
async def show_stars(message: types.Message):
    user_id = str(message.from_user.id)
    data = users.get(user_id, {"stars": 0, "ton_paid": 0})
    await message.answer(
        f"📊 <b>Твои балансы:</b>\n"
        f"✨ Звёзды: {data['stars']}\n"
        f"💎 Оплачено TON: {data['ton_paid']}",
        parse_mode="HTML"
    )

@dp.message_handler()
async def fallback(message: types.Message):
    await message.answer("ℹ️ Используй команды: /pay_ton, /pay_stars, /stars, /ping")

# Пинг каждые 10 минут
async def self_ping():
    while True:
        try:
            async with ClientSession() as session:
                async with session.get(WEBHOOK_HOST) as resp:
                    logger.info(f"Ping result: {resp.status}")
        except Exception as e:
            logger.error(f"Ping failed: {e}")
        await asyncio.sleep(300)

# Проверка оплат TON
async def check_ton_payments():
    global last_balance
    while True:
        try:
            async with ClientSession() as session:
                async with session.get(
                    f"https://toncenter.com/api/v2/getAddressBalance?address={TON_ADDRESS}", timeout=5
                ) as resp:
                    result = await resp.json()
                    balance = int(result["result"]) / 1e9

            if balance > last_balance:
                delta = round(balance - last_balance, 4)
                last_balance = balance

                for user_id in users:
                    users[user_id]["ton_paid"] += delta
                    try:
                        await bot.send_message(
                            int(user_id),
                            f"💸 Получено {delta} TON. Спасибо за оплату!"
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить сообщение {user_id}: {e}")

        except Exception as e:
            logger.error(f"TON CHECK ERROR: {e}")
        await asyncio.sleep(10)

# Обработка вебхуков
async def webhook_handler(request):
    try:
        data = await request.json()
        logger.info(f"Received update: {data}")

        from aiogram import Bot  # для set_current
        Bot.set_current(bot)
        update = types.Update(**data)
        await dp.process_update(update)

        return Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(text="OK")

# Запуск сервера
async def start_server():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, webhook_handler)

    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    logger.info(f"Server started on port {PORT}")

    asyncio.create_task(check_ton_payments())
    asyncio.create_task(self_ping())

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

