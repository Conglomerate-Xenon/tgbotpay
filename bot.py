import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web, ClientSession
from aiohttp.web_response import Response
from dotenv import load_dotenv

from db import init_db, add_user, get_random_question, update_score, get_top_users

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # например, https://your-app.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", "10000"))

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
init_db()

# Словарь для хранения состояния пользователя (текущий вопрос)
user_states = {}

# Команда /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    add_user(message.from_user.id, message.from_user.username or "Anon")
    await message.answer("👋 Добро пожаловать в Квиз-Битву! Напиши /quiz чтобы начать.")

# Команда /quiz
@dp.message_handler(commands=["quiz"])
async def quiz(message: types.Message):
    q = get_random_question()
    if not q:
        await message.answer("Нет вопросов в базе.")
        return

    question_id, text, *options, correct = q
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    for i, opt in enumerate(options):
        keyboard.add(KeyboardButton(f"{i+1}. {opt}"))

    user_states[message.from_user.id] = (question_id, correct)
    await message.answer(f"🧠 Вопрос:\n{text}", reply_markup=keyboard)

# Команда /top
@dp.message_handler(commands=["top"])
async def top(message: types.Message):
    top_users = get_top_users()
    if not top_users:
        await message.answer("Рейтинг пока пуст.")
        return
    msg = "🏆 Топ игроков:\n"
    for i, (username, score) in enumerate(top_users, 1):
        msg += f"{i}. {username} — {score} очков\n"
    await message.answer(msg)

# Обработка ответа пользователя
@dp.message_handler()
async def handle_answer(message: types.Message):
    state = user_states.get(message.from_user.id)
    if not state:
        return

    try:
        answer = int(message.text[0])
    except ValueError:
        return

    question_id, correct = state
    if answer == correct:
        update_score(message.from_user.id, 10)
        await message.answer("✅ Верно! +10 очков.")
    else:
        await message.answer("❌ Неверно.")
    user_states.pop(message.from_user.id)

    await asyncio.sleep(1)
    await quiz(message)  # следующий вопрос

# Пинг каждые 5 минут (чтобы не "уснул" Render)
async def self_ping():
    while True:
        try:
            async with ClientSession() as session:
                async with session.get(WEBHOOK_HOST) as resp:
                    logger.info(f"Ping result: {resp.status}")
        except Exception as e:
            logger.error(f"Ping failed: {e}")
        await asyncio.sleep(300)

# Обработка входящих вебхуков
async def webhook_handler(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.process_update(update)
        return Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(text="ERROR")

# Запуск сервера
async def start_server():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, webhook_handler)

    # Установка вебхука Telegram
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    logger.info(f"Server started on port {PORT}")
    asyncio.create_task(self_ping())

    while True:
        await asyncio.sleep(3600)

# Запуск
if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
