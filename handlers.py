from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import MessageCantBeEdited, InlineKeyboardExpected
from bot import dp
from database import register_user_if_not_exists, log_query, find_cities_in_db
from weather import get_weather_label, get_detailed_weather, check_city_exists
from keyboards import main_menu, get_back_keyboard
from states import States
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton  # Убедитесь, что импорты есть

# Храним состояние пагинации в FSM
async def set_pagination_state(state: FSMContext, cities: list, page: int = 1):
    await state.update_data(cities=cities, current_page=page)

async def get_pagination_state(state: FSMContext) -> tuple[list, int]:
    data = await state.get_data()
    return data.get("cities", []), data.get("current_page", 1)

def register_handlers(dp: Dispatcher):
    @dp.message_handler(commands=['start'], state='*')
    async def cmd_start(message: types.Message, state: FSMContext):
        await state.finish()
        register_user_if_not_exists(message.from_user.id)

        text = (
            f"Добро пожаловать в меню, {message.from_user.first_name}!\n\n"
            "Я бот, который покажет погоду.\n"
            "Выберите нужный пункт меню:"
        )
        kb = main_menu  # ReplyKeyboardMarkup для главного меню
        try:
            await message.edit_text(text, reply_markup=kb, parse_mode="Markdown")  # Пытаемся отредактировать
        except (MessageCantBeEdited, InlineKeyboardExpected):
            # Если сообщение нельзя отредактировать или ожидается инлайн-клавиатура, отправляем новое
            await message.answer(text, reply_markup=kb, parse_mode="Markdown")

    @dp.message_handler(lambda msg: msg.text == "🌡 Посмотреть температуру городов", state='*')
    async def handle_view_cities(message: types.Message, state: FSMContext):
        kb = get_back_keyboard()
        text = (
            "📝 Введите названия городов через запятую.\n\n"
            "Например: «Волгоград, Воронеж, Волжский, Пермь»"
        )
        try:
            await message.edit_text(text, reply_markup=kb)  # Используем edit_text для обновления
        except MessageCantBeEdited:
            await message.answer(text, reply_markup=kb)  # Если нельзя отредактировать, отправляем новое

        await States.waiting_for_cities.set()

    @dp.callback_query_handler(lambda c: c.data == "back_to_menu", state='*')
    async def callback_back(query: types.CallbackQuery, state: FSMContext):
        await query.answer()
        await state.finish()

        # Активируем команду /start, но с использованием edit_text, если возможно
        try:
            await cmd_start(query.message, state)
        except InlineKeyboardExpected:
            # Если сообщение содержит инлайн-клавиатуру, отправляем новое сообщение
            await query.message.answer(
                f"Добро пожаловать, {query.from_user.first_name}!\n\n"
                "Я бот, который покажет погоду — *только из бесплатных данных*.\n"
                "Выберите нужный пункт меню:",
                reply_markup=main_menu,
                parse_mode="Markdown"
            )

    @dp.message_handler(lambda msg: msg.text == "👤 Мой профиль", state='*')
    async def handle_my_profile(message: types.Message, state: FSMContext):
        user = message.from_user
        back_kb = get_back_keyboard()

        username = user.username if user.username else "(нет)"
        language = user.language_code if user.language_code else "(неизвестно)"

        text = (
            "👤 Мой профиль:\n\n"
            f"• Имя: {user.first_name}\n"
            f"• ID: {user.id}\n"
            f"• Ваш tg: @{username}\n"
            f"• Язык: {language}"
        )
        try:
            await message.edit_text(text, reply_markup=back_kb)  # Используем edit_text
        except MessageCantBeEdited:
            await message.answer(text, reply_markup=back_kb)  # Если нельзя отредактировать, отправляем новое

    @dp.message_handler(state=States.waiting_for_cities)
    async def process_city_list(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        user_text = message.text.strip()
        log_query(user_id, user_text)

        if not user_text:
            kb = get_back_keyboard()
            try:
                await message.edit_text("❌ Вы не ввели никаких городов", reply_markup=kb)  # Используем edit_text
            except MessageCantBeEdited:
                await message.answer("❌ Вы не ввели никаких городов", reply_markup=kb)  # Если нельзя, отправляем новое
            return

        # Разделяем города и убираем повторения
        cities = list(dict.fromkeys([c.strip() for c in user_text.split(",") if c.strip()]))  # Уникальные города
        if not cities:
            kb = get_back_keyboard()
            try:
                await message.edit_text("❌ Вы не ввели никаких городов", reply_markup=kb)  # Используем edit_text
            except MessageCantBeEdited:
                await message.answer("❌ Вы не ввели никаких городов", reply_markup=kb)  # Если нельзя, отправляем новое
            return

        # Сначала проверяем города в базе данных
        found, not_found = find_cities_in_db(cities)

        # Проверяем не найденные города через API
        additional_found = []
        for city in not_found:
            exists, label = check_city_exists(city)
            if exists:
                additional_found.append((city, city))  # Используем оригинальное имя города как официальное

        # Обновляем found, добавляя города, найденные через API
        if additional_found:
            found.extend(additional_found)
            # Удаляем найденные города из not_found, чтобы избежать дублирования
            not_found = [city for city in not_found if not any(city == f[0] for f in additional_found)]

        # Если есть хотя бы один правильный город (found не пустой)
        if found:
            # Сохраняем список уникальных городов для пагинации
            await set_pagination_state(state, found, page=1)
            await show_cities_page(message, state)
        # Если ни один город не найден (found пустой)
        else:
            not_found_list = ", ".join(not_found) if not_found else "указанные"
            kb = get_back_keyboard()
            try:
                await message.edit_text(f"❌ Таких городов, как {not_found_list}, нет", reply_markup=kb)  # Используем edit_text
            except MessageCantBeEdited:
                await message.answer(f"❌ Таких городов, как {not_found_list}, нет", reply_markup=kb)  # Если нельзя, отправляем новое

    async def show_cities_page(message: types.Message | types.CallbackQuery, state: FSMContext):
        cities, current_page = await get_pagination_state(state)
        if not cities:
            kb = get_back_keyboard()
            if isinstance(message, types.Message):
                try:
                    await message.edit_text("❌ Список городов пуст", reply_markup=kb)  # Используем edit_text
                except MessageCantBeEdited:
                    await message.answer("❌ Список городов пуст", reply_markup=kb)  # Если нельзя, отправляем новое
            else:
                try:
                    await message.message.edit_text("❌ Список городов пуст", reply_markup=kb)  # Используем edit_text
                except MessageCantBeEdited:
                    await message.message.answer("❌ Список городов пуст", reply_markup=kb)  # Если нельзя, отправляем новое
            return

        ITEMS_PER_PAGE = 4
        total_pages = (len(cities) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        if current_page < 1 or current_page > total_pages:
            current_page = 1

        start_idx = (current_page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_cities = cities[start_idx:end_idx]

        weather_kb = InlineKeyboardMarkup(row_width=1)

        # Добавляем кнопки для городов на текущей странице
        for user_city, official_city in page_cities:
            label = get_weather_label(official_city)
            cb_data = f"details|{official_city}"
            weather_kb.add(InlineKeyboardButton(label, callback_data=cb_data))

        # Добавляем кнопки пагинации
        pagination_kb = InlineKeyboardMarkup(row_width=3)
        if current_page > 1:
            pagination_kb.insert(InlineKeyboardButton("⬅️ Предыдущая", callback_data=f"page_{current_page-1}"))
        pagination_kb.insert(InlineKeyboardButton(f"Страница {current_page}/{total_pages}", callback_data="none"))
        if current_page < total_pages:
            pagination_kb.insert(InlineKeyboardButton("➡️ Следующая", callback_data=f"page_{current_page+1}"))

        # Объединяем кнопки городов и пагинации
        weather_kb.inline_keyboard.extend(pagination_kb.inline_keyboard)
        weather_kb.add(InlineKeyboardButton("🔙 Вернуться", callback_data="back_to_menu"))

        try:
            if isinstance(message, types.Message):
                await message.edit_text("Вот погода по вашим городам (см. кнопки):", reply_markup=weather_kb)
            else:
                await message.message.edit_text("Вот погода по вашим городам (см. кнопки):", reply_markup=weather_kb)
        except (MessageCantBeEdited, InlineKeyboardExpected):
            # Если сообщение нельзя отредактировать или ожидается инлайн-клавиатура, отправляем новое
            if isinstance(message, types.Message):
                await message.answer("Вот погода по вашим городам (см. кнопки):", reply_markup=weather_kb)
            else:
                await message.message.answer("Вот погода по вашим городам (см. кнопки):", reply_markup=weather_kb)

    @dp.callback_query_handler(lambda c: c.data.startswith("page_"), state=States.waiting_for_cities)
    async def handle_pagination(query: types.CallbackQuery, state: FSMContext):
        await query.answer()
        page = int(query.data.split("_")[1])
        cities, _ = await get_pagination_state(state)  # Ждем результат корутины
        await set_pagination_state(state, cities, page=page)
        await show_cities_page(query, state)

    @dp.callback_query_handler(lambda c: c.data.startswith("details|"), state='*')
    async def callback_details(query: types.CallbackQuery, state: FSMContext):
        await query.answer()
        _, city_name = query.data.split("|", 1)
        info = get_detailed_weather(city_name)
        
        # Создаем клавиатуру с кнопкой "Вернуться"
        back_kb = InlineKeyboardMarkup()
        back_kb.add(InlineKeyboardButton("🔙 Вернуться", callback_data="back_to_menu"))
        
        try:
            await query.message.edit_text(info, reply_markup=back_kb)  # Используем edit_text
        except (MessageCantBeEdited, InlineKeyboardExpected):
            await query.message.answer(info, reply_markup=back_kb)  # Если нельзя, отправляем новое

    @dp.message_handler(content_types=['text'], state='*')
    async def fallback_text(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        user_text = message.text.strip()
        log_query(user_id, user_text)

        try:
            await message.edit_text("Пожалуйста, используйте кнопки или введите /start, чтобы вернуться в меню.")  # Используем edit_text
        except (MessageCantBeEdited, InlineKeyboardExpected):
            await message.answer("Пожалуйста, используйте кнопки или введите /start, чтобы вернуться в меню.")  # Если нельзя, отправляем новое