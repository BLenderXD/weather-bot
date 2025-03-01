import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

TELEGRAM_BOT_TOKEN = "7888848050:AAHpa0-xGhSEFi1SFbyqUe_J5OMqB0zgy6I"

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)