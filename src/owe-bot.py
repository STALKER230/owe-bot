from __future__ import annotations

from datetime import datetime
import telebot
import os
from dotenv import load_dotenv
from telebot import types
import sqlite3
from dataclasses import dataclass
from telebot.types import Message, CallbackQuery

connection = sqlite3.connect("my_database.db", check_same_thread=False)


def init_database():
    cursor = connection.cursor()

    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS Names (
    name_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS Transactions (
    trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    commentary TEXT NOT NULL,
    date INTEGER NOT NULL,
    FOREIGN KEY(person_id) REFERENCES Names(name_id) ON DELETE CASCADE
    )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_userid ON Names (user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_persid ON Transactions (person_id)")

    connection.commit()


@dataclass(slots=True)
class Name:
    id: int | None
    user_id: int
    user_name: str

    def add_name(self):
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO Names (user_id, user_name) VALUES (?,?)",
            (self.user_id, self.user_name),
        )
        connection.commit()

    @staticmethod
    def get_names(user_id: int) -> list[Name]:
        cursor2 = connection.cursor()
        cursor2.execute("SELECT * FROM Names WHERE user_id = ?", (user_id,))
        results = cursor2.fetchall()
        cursor2.close()
        return [Name(*i) for i in results]

    @staticmethod
    def edit(id: int, new_name: str):
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE Names SET user_name = ? WHERE name_id = ?", (new_name, id)
        )
        cursor.close()
        connection.commit()

    @staticmethod
    def delete(id: int):
        cursor = connection.cursor()
        cursor.execute("DELETE FROM Names WHERE name_id = ?", (id,))
        cursor.close()
        connection.commit()


@dataclass(slots=True)
class Transactions:
    id: int | None
    amount: int
    person_id: int
    commentary: str
    date: datetime

    def __init__(
        self, id: int | None, amount: int, person_id: int, commentary: str, date: int
    ):
        self.id = id
        self.amount = amount
        self.person_id = person_id
        self.commentary = commentary
        self.date = datetime.fromtimestamp(date)

    def __str__(self) -> str:
        return f"{self.date:%d/%m/%Y %H:%M}: {self.commentary}"

    def add_trans(self):
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO Transactions (amount, person_id, commentary, date) VALUES (?, ?, ?, ?)",
            (self.amount, self.person_id, self.commentary, int(self.date.timestamp())),
        )
        cursor.close()
        connection.commit()

    @staticmethod
    def get_all_transactions(person_id: int) -> list[Transactions]:
        cursor2thegreatreturn = connection.cursor()
        cursor2thegreatreturn.execute(
            "SELECT * FROM Transactions WHERE person_id = ?", (person_id,)
        )
        results = cursor2thegreatreturn.fetchall()
        cursor2thegreatreturn.close()
        return [Transactions(*i) for i in results]


init_database()

load_dotenv()

bot = telebot.TeleBot(os.getenv("TOKEN"))


@bot.message_handler(commands=["start"])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("Добавить человека", callback_data="add")
    btn2 = types.InlineKeyboardButton("Мои записи", callback_data="existing")
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, text="Добрый день!", reply_markup=markup)


@bot.callback_query_handler(func=lambda callback: callback.data == "existing")
def ex(callback: CallbackQuery):
    markup = types.InlineKeyboardMarkup()
    a = Name.get_names(callback.from_user.id)
    for i in a:
        butt = types.InlineKeyboardButton(i.user_name, callback_data=f"user {i.id}")
        markup.add(butt)
    bot.send_message(
        callback.message.chat.id,
        text=f"Список должников: {len(a)} шт",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda callback: callback.data.startswith("user "))
def person_info(callback: CallbackQuery):
    summ = 0
    user_id = int(callback.data[5:])
    personal_trans = Transactions.get_all_transactions(user_id)
    markup = types.InlineKeyboardMarkup()
    butt1 = types.InlineKeyboardButton(
        text="Добавить транзакцию", callback_data=f"addtrans {user_id}"
    )
    butt2 = types.InlineKeyboardButton(
        text="Удалить должника", callback_data=f"delete {user_id}"
    )
    markup.add(butt1, butt2)
    if len(personal_trans) == 0:
        bot.send_message(
            callback.message.chat.id, "Транзакций нет", reply_markup=markup
        )
        return
    for i in personal_trans:
        summ += i.amount
        text = f"Общая сумма: {summ}\n" + "\n".join(map(str, personal_trans))
    bot.send_message(callback.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda callback: callback.data.startswith("delete "))
def delete_person(callback: CallbackQuery):
    user_id = int(callback.data[7:])
    Name.delete(user_id)
    bot.send_message(callback.message.chat.id, text="Должник успешно удален")
    start(callback.message)


@bot.callback_query_handler(func=lambda callback: callback.data.startswith("addtrans "))
def trans(callback: CallbackQuery):
    user_id = int(callback.data[9:])
    bot.send_message(callback.message.chat.id, "Введите сумму долга")
    bot.register_next_step_handler(
        callback.message, lambda message: add_amount(user_id, message)
    )


def add_amount(user_id: int, message: Message):
    amount = int(message.text)
    bot.send_message(message.chat.id, "Введите комментарий")
    bot.register_next_step_handler(
        message, lambda message: add_commentary(amount, user_id, message)
    )


def add_commentary(amount: int, user_id: int, message: Message):
    Transactions(None, amount, user_id, message.text.strip(), message.date).add_trans()
    bot.send_message(message.chat.id, "Транзакция успешно добавлена")
    start(message)


@bot.callback_query_handler(func=lambda callback: callback.data == "add")
def add(callback: CallbackQuery):
    bot.send_message(callback.message.chat.id, "Введите имя нового должника>:)")
    bot.register_next_step_handler(callback.message, add_user)


def add_user(message: Message):
    Name(None, message.from_user.id, message.text.strip()).add_name()
    bot.send_message(message.chat.id, "Должник добавлен!")


bot.polling(none_stop=True)


connection.close()
