import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Callable, Dict, Any, Awaitable

import config
from database import TradingDatabase
from analytics import TradingAnalytics

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = TradingDatabase()
analytics = TradingAnalytics()
scheduler = AsyncIOScheduler()


# ============= MIDDLEWARE ДЛЯ АВТОРИЗАЦИИ =============
class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки доступа к боту"""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        # Проверяем только сообщения
        if isinstance(event, Message):
            user_id = event.from_user.id

            # Если пользователь не админ - блокируем
            if user_id != config.ADMIN_USER_ID:
                logger.warning(
                    f"Unauthorized access attempt from user {user_id} "
                    f"(@{event.from_user.username or 'no_username'})"
                )

                await event.answer(
                    "⛔ <b>Доступ запрещён</b>\n\n"
                    f"Ваш ID: <code>{user_id}</code>\n"
                    f"Username: @{event.from_user.username or 'не указан'}\n\n"
                    "Это приватный трейдинг-журнал."
                )

                # Опционально: уведомляем админа о попытке доступа
                try:
                    await bot.send_message(
                        config.ADMIN_USER_ID,
                        f"⚠️ <b>Попытка несанкционированного доступа</b>\n\n"
                        f"👤 User ID: <code>{user_id}</code>\n"
                        f"📝 Username: @{event.from_user.username or 'нет'}\n"
                        f"🏷 Имя: {event.from_user.full_name}\n"
                        f"💬 Сообщение: <code>{event.text[:100] if event.text else 'нет текста'}</code>"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin about unauthorized access: {e}")

                return  # Прерываем обработку

        # Если всё ОК - продолжаем обработку
        return await handler(event, data)


# ============= ФУНКЦИИ ПАРСИНГА =============
def parse_trade(text: str) -> dict:
    """
    Парсинг сообщения о сделке
    Формат: BTC long 45000 46000 +100 стратегия
    или: ETH short 3000 2950 -50 фомо отыгрыш комментарий
    """
    parts = text.strip().split()

    if len(parts) < 5:
        raise ValueError("Недостаточно данных. Формат: ПАРА ТИП ВХОД ВЫХОД PNL [ТЕГИ]")

    pair = parts[0].upper()
    trade_type = parts[1].lower()

    if trade_type not in ['long', 'short', 'лонг', 'шорт']:
        raise ValueError("Тип должен быть: long/short")

    try:
        entry = float(parts[2])
        exit_price = float(parts[3])
        pnl_str = parts[4]

        # Убираем символы + и $
        pnl_usd = float(pnl_str.replace('+', '').replace('$', ''))

        # Расчёт % (упрощённо)
        pnl_pct = (exit_price - entry) / entry * 100
        if trade_type in ['short', 'шорт']:
            pnl_pct = -pnl_pct

    except ValueError:
        raise ValueError("Цены и PNL должны быть числами")

    # Остальное - теги и комментарий
    tags_and_comment = ' '.join(parts[5:]).lower() if len(parts) > 5 else ''

    # Определяем категорию
    category = 'неизвестно'
    if any(tag in tags_and_comment for tag in config.STRATEGY_TAGS):
        category = 'стратегия'
    elif any(tag in tags_and_comment for tag in config.IMPULSE_TAGS):
        category = 'импульс'

    return {
        'pair': pair,
        'type': trade_type,
        'entry': entry,
        'exit': exit_price,
        'pnl_usd': pnl_usd,
        'pnl_pct': round(pnl_pct, 2),
        'category': category,
        'tags': tags_and_comment,
        'comment': tags_and_comment
    }


# ============= КОМАНДЫ БОТА =============
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    help_text = f"""
👋 <b>Привет, {message.from_user.first_name}!</b>

Я твой трейдинг-журнал.

📝 <b>Как записать сделку:</b>
Просто пришли мне сообщение в формате:

<code>ПАРА ТИП ВХОД ВЫХОД PNL ТЕГИ</code>

<b>Примеры:</b>
<code>BTC long 45000 46000 +100 стратегия</code>
<code>ETH short 3000 2950 -50 фомо отыгрыш</code>
<code>SOL long 100 105 +25 план терпение</code>

<b>Теги для стратегии:</b> стратегия, план
<b>Теги для импульса:</b> фомо, импульс, отыгрыш, тильт

📊 <b>Команды:</b>
/today - статистика за сегодня
/week - статистика за неделю
/report - полный недельный отчёт
/last - последние 5 сделок
/myid - узнать свой Telegram ID
"""
    await message.answer(help_text)


@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    """Показать свой Telegram ID"""
    await message.answer(
        f"🆔 <b>Ваши данные:</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{message.from_user.username or 'не указан'}\n"
        f"Имя: {message.from_user.full_name}\n\n"
        f"{'✅ Вы администратор этого бота' if message.from_user.id == config.ADMIN_USER_ID else '⚠️ У вас нет прав администратора'}"
    )


@dp.message(Command("today"))
async def cmd_today(message: Message):
    """Статистика за сегодня"""
    stats = await db.get_today_stats()

    response = f"""
📊 <b>Сегодня:</b>

Сделок: {stats['count']}
P/L: {stats['pnl']:+.2f} USD

🎯 По стратегии: {stats['strategy_count']}
😤 Импульсивных: {stats['impulse_count']}
"""

    if stats['impulse_count'] > stats['strategy_count'] and stats['impulse_count'] > 0:
        response += "\n⚠️ <b>Внимание!</b> Импульсивных сделок больше, чем по стратегии!"

    await message.answer(response)


@dp.message(Command("week"))
async def cmd_week(message: Message):
    """Статистика за неделю (краткая)"""
    df = await db.get_trades(days=7)

    if df.empty:
        await message.answer("📊 За неделю сделок не было")
        return

    metrics = analytics.calculate_metrics(df)

    response = f"""
📊 <b>Неделя:</b>

Сделок: {metrics['total_trades']}
P/L: {metrics['total_pnl']:+.2f} USD
Win Rate: {metrics['win_rate']:.1f}%
Profit Factor: {metrics['profit_factor']:.2f}

Используй /report для подробного отчёта
"""
    await message.answer(response)


@dp.message(Command("report"))
async def cmd_report(message: Message):
    """Полный недельный отчёт"""
    df = await db.get_trades(days=7)
    report = analytics.generate_weekly_report(df)
    await message.answer(report)


@dp.message(Command("last"))
async def cmd_last(message: Message):
    """Последние 5 сделок"""
    trades = await db.get_last_trades(limit=5)

    if not trades:
        await message.answer("📊 Сделок пока нет")
        return

    response = "📋 <b>Последние 5 сделок:</b>\n\n"

    for i, trade in enumerate(trades, 1):
        pnl_emoji = "📈" if trade['pnl_usd'] > 0 else "📉"
        cat_emoji = "🎯" if trade['category'] == 'стратегия' else "😤"

        response += f"{i}. {pnl_emoji} {trade['pair']} {trade['trade_type']}\n"
        response += f"   {cat_emoji} {trade['pnl_usd']:+.2f} USD ({trade['category']})\n"
        response += f"   {trade['trade_date']} {trade['trade_time']}\n\n"

    await message.answer(response)


@dp.message(F.text)
async def handle_trade(message: Message):
    """Обработка сделки"""
    try:
        trade_data = parse_trade(message.text)

        if await db.add_trade(trade_data):
            # Получаем статистику за сегодня
            stats = await db.get_today_stats()

            response = f"✅ <b>Сделка записана</b>\n\n"
            response += f"📊 <b>Сегодня:</b> {stats['count']} сделок, {stats['pnl']:+.2f} USD\n"

            if stats['impulse_count'] >= 2:
                response += "\n⚠️ <b>ВНИМАНИЕ!</b>\n"
                response += f"Уже {stats['impulse_count']} импульсивных сделок сегодня.\n"
                response += "💡 Возьми паузу на 1 час!"

            # Если это импульсивная сделка
            if trade_data['category'] == 'импульс':
                response += "\n😤 Помечено как <b>импульсивная</b> сделка"

            await message.answer(response)
        else:
            await message.answer("❌ Ошибка при сохранении сделки")

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка: {str(e)}\n\nИспользуй формат:\n<code>BTC long 45000 46000 +100 стратегия</code>")
    except Exception as e:
        logger.error(f"Error handling trade: {e}")
        await message.answer("❌ Произошла ошибка. Проверь формат сообщения.")


# ============= АВТОМАТИЧЕСКИЕ ОТЧЁТЫ =============
async def send_daily_reminder():
    """Ежедневное напоминание (в 20:00)"""
    stats = await db.get_today_stats()

    if stats['count'] == 0:
        return

    message = f"""
🌙 <b>Дневной итог:</b>

Сделок: {stats['count']}
P/L: {stats['pnl']:+.2f} USD

🎯 По стратегии: {stats['strategy_count']}
😤 Импульсивных: {stats['impulse_count']}

{'⚠️ Много импульсивных сделок! Проанализируй причины.' if stats['impulse_count'] > 2 else ''}
"""

    try:
        await bot.send_message(config.ADMIN_USER_ID, message)
    except Exception as e:
        logger.error(f"Error sending daily reminder: {e}")


async def send_weekly_report():
    """Еженедельный отчёт (воскресенье 18:00)"""
    df = await db.get_trades(days=7)
    report = analytics.generate_weekly_report(df)

    try:
        await bot.send_message(config.ADMIN_USER_ID, report)
    except Exception as e:
        logger.error(f"Error sending weekly report: {e}")


# ============= LIFECYCLE =============
async def on_startup():
    """Действия при запуске бота"""
    await db.connect()
    await db.init_db()
    logger.info("Bot started successfully")

    # Отправляем уведомление админу о запуске
    try:
        await bot.send_message(
            config.ADMIN_USER_ID,
            "🤖 <b>Бот запущен</b>\n\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "Всё готово к работе!"
        )
    except Exception as e:
        logger.error(f"Failed to send startup notification: {e}")


async def on_shutdown():
    """Действия при остановке бота"""
    await db.close()
    logger.info("Bot stopped")


async def main():
    # Регистрируем middleware ДО старта polling
    dp.message.middleware(AuthMiddleware())

    # Настройка планировщика
    scheduler.add_job(
        send_daily_reminder,
        'cron',
        hour=config.ANALYSIS_HOUR,
        minute=0
    )

    scheduler.add_job(
        send_weekly_report,
        'cron',
        day_of_week=config.WEEKLY_REPORT_DAY,
        hour=config.WEEKLY_REPORT_HOUR,
        minute=0
    )

    scheduler.start()

    # Запуск бота
    await on_startup()

    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())