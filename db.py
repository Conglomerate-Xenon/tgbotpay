import sqlite3
from random import choice

# Подключаемся к базе данных (если нет — будет создана)
conn = sqlite3.connect("quiz.db")
cursor = conn.cursor()

# Инициализация базы данных: создаём таблицы, если не существуют
def init_db():
    # Таблица пользователей: id, имя пользователя и очки
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        score INTEGER DEFAULT 0
    )''')

    # Таблица вопросов: текст вопроса, 4 варианта ответа и номер правильного
    cursor.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY,
        text TEXT,
        option1 TEXT,
        option2 TEXT,
        option3 TEXT,
        option4 TEXT,
        correct INTEGER
    )''')
    conn.commit()

# Получить случайный вопрос из базы
def get_random_question():
    cursor.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
    return cursor.fetchone()

# Добавить нового пользователя (если его ещё нет)
def add_user(user_id, username):
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

# Обновить счёт игрока (добавить очки)
def update_score(user_id, points):
    cursor.execute("UPDATE users SET score = score + ? WHERE id = ?", (points, user_id))
    conn.commit()

# Получить топ-10 пользователей по рейтингу
def get_top_users():
    cursor.execute("SELECT username, score FROM users ORDER BY score DESC LIMIT 10")
    return cursor.fetchall()
