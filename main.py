from bot import bot, dp
from database import create_tables
from handlers import register_handlers
from aiogram.utils import executor

def main():
    create_tables()  # Создаем таблицы при запуске
    register_handlers(dp)  # Регистрируем обработчики
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    main()