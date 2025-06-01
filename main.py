import re
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import BotCommand
from sqlighter import DBManager
import config as cnfg
from time_table_parses import parse
from storage import StorageService
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Инициализация
bot = Bot(
    token=cnfg.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
db = DBManager()
storage = StorageService()
scheduler = AsyncIOScheduler()

# Регулярные выражения
GROUP_REGEX = re.compile(r"^[А-Яа-яA-Za-z]{4}-\d{2}-\d{2}$")
TEACHER_REGEX = re.compile(r"^[А-Яа-яA-Za-zёЁ]+ [А-ЯA-Z]\.[А-ЯA-Z]\.$")

@dp.message(CommandStart())
async def handle_start(message: Message):
    db.add_new_user(message.from_user.id)
    await message.answer(
        "👋 Привет! Введи <b>группу</b> (например, <code>ИВТ-21-01</code>) "
        "или <b>ФИО преподавателя</b> (например, <code>Иванов И.П.</code>) для получения расписания."
    )

def format_schedule_by_days(schedule, for_group=True) -> str:
    days_order = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]

    # Время пар по номеру
    couple_times = {
        1: "9:00 - 10:30",
        2: "10:40 - 12:10",
        3: "12:40 - 14:10",
        4: "14:20 - 15:50",
        5: "16:20 - 17:50",
        6: "18:00 - 19:30",
    }

    schedule_by_day = {day: [] for day in days_order}
    for entry in schedule:
        day = entry['day_of_week']
        if day in schedule_by_day:
            schedule_by_day[day].append(entry)

    result_lines = []
    for day in days_order:
        day_entries = schedule_by_day[day]
        if not day_entries:
            continue

        result_lines.append(f"📅 <b>{day}</b>:\n")
        result_lines.append("<pre>")

        header = f"{'Пара':<15}  {'1 неделя':<45}  {'2 неделя':<45}"
        result_lines.append(header)
        result_lines.append("-" * 105)

        couples_nums = sorted(set(e['couple_num'] for e in day_entries))
        for couple_num in couples_nums:
            week1_entries = [e for e in day_entries if e['couple_num'] == couple_num and e['week_num'] == 1]
            week2_entries = [e for e in day_entries if e['couple_num'] == couple_num and e['week_num'] == 2]

            def fmt(e):
                base = f"{e['course_name']}"
                if for_group:
                    base += f", {e['teacher_full_name']}, {e['auditorium']}"
                else:
                    base += f", {e['group_id']}, {e['auditorium']}"
                return base

            w1_text = ", ".join(fmt(e) for e in week1_entries) if week1_entries else "—"
            w2_text = ", ".join(fmt(e) for e in week2_entries) if week2_entries else "—"

            def clip_text(text, max_len=45):
                return text if len(text) <= max_len else text[: max_len - 3] + "..."

            w1_text = clip_text(w1_text)
            w2_text = clip_text(w2_text)

            # Добавляем время пары в скобках рядом с номером
            time_str = couple_times.get(couple_num, "—")
            pair_str = f"{couple_num} ({time_str})"

            line = f"{pair_str:<15}  {w1_text:<45}  {w2_text:<45}"
            result_lines.append(line)

        result_lines.append("</pre>\n")

    return "\n".join(result_lines)



@dp.message(F.text)
async def handle_text(message: Message):
    text = message.text.strip()

    if GROUP_REGEX.match(text):
        schedule = db.get_schedule_by_group(text)
        if schedule:
            response = format_schedule_by_days(schedule, for_group=True)
        else:
            response = f"📭 Расписание для группы <b>{text}</b> не найдено."
        await message.answer(response)

    elif TEACHER_REGEX.match(text):
        schedule = db.get_schedule_by_teacher(text)
        if schedule:
            response = format_schedule_by_days(schedule, for_group=False)
        else:
            response = f"📭 Расписание для преподавателя <b>{text}</b> не найдено."
        await message.answer(response)

    else:
        await message.answer(
            "⚠ Введите <b>название группы</b> (например, <code>ИВТ-21-01</code>) "
            "или <b>ФИО преподавателя</b> (например, <code>Иванов И.П.</code>)"
        )

async def check_updates_and_notify():
    last_update = db.get_last_update()
    s3_update_time = storage.check_and_download_if_updated(last_update)
    if s3_update_time:
        print("📥 Обнаружено новое расписание. Загружаю...")
        try:
            groups, teachers, time_table_info = parse(cnfg.EXCEL_NAME)
            db.create_or_update_time_table(groups, teachers, time_table_info)
            db.set_last_update(s3_update_time)

            user_ids = db.get_all_user_ids()
            for user_id in user_ids:
                try:
                    await bot.send_message(user_id, "📢 Расписание было обновлено!")
                except Exception as e:
                    print(f"Ошибка при отправке сообщения {user_id}: {e}")
        except Exception as e:
            print(f"Ошибка при обновлении расписания: {e}")
async def main():
    # Команды бота (для меню Telegram)
    await bot.set_my_commands([
        BotCommand(command="start", description="Запуск бота"),
    ])

    scheduler.add_job(check_updates_and_notify, "interval", minutes=1)
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    # При первом запуске проверяем, нужно ли загрузить расписание
    last_update = db.get_last_update()
    if last_update is None:
        print("🕘 Последнее обновление не найдено в БД. Загружаю расписание...")
        from datetime import timezone
        fake_old_time = datetime(1970, 1, 1, tzinfo=timezone.utc)
        s3_update_time = storage.check_and_download_if_updated(fake_old_time)

        if s3_update_time:
            try:
                groups, teachers, time_table_info = parse(cnfg.EXCEL_NAME)
                db.create_or_update_time_table(groups, teachers, time_table_info)
                db.set_last_update(s3_update_time)
                print("✅ Расписание загружено при инициализации.")
            except Exception as e:
                print(f"❌ Ошибка при инициализации расписания: {e}")
        else:
            print("⚠️ Не удалось загрузить обновлённое расписание при старте.")
    else:
        # Загружаем в любом случае в БД, если нужно (без запроса к S3)
        groups, teachers, time_table_info = parse(cnfg.EXCEL_NAME)
        db.create_or_update_time_table(groups, teachers, time_table_info)

    # Старт бота
    asyncio.run(main())