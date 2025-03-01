from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(
    KeyboardButton("🌡 Посмотреть температуру городов"),
    KeyboardButton("👤 Мой профиль")
)

def get_back_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Вернуться", callback_data="back_to_menu"))
    return kb