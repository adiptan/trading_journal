import asyncpg
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Optional
import config
import logging

logger = logging.getLogger(__name__)


class TradingDatabase:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Создание пула соединений"""
        try:
            self.pool = await asyncpg.create_pool(
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                min_size=1,
                max_size=10
            )
            logger.info("Database pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise

    async def close(self):
        """Закрытие пула соединений"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

    async def init_db(self):
        """Инициализация БД (создание таблиц если их нет)"""
        async with self.pool.acquire() as conn:
            # Читаем SQL из файла
            try:
                with open('init_db.sql', 'r', encoding='utf-8') as f:
                    sql = f.read()
                    # Выполняем каждую команду отдельно
                    for statement in sql.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
                logger.info("Database initialized successfully")
            except FileNotFoundError:
                logger.warning("init_db.sql not found, skipping initialization")
            except Exception as e:
                logger.error(f"Error initializing database: {e}")

    async def add_trade(self, trade_data: Dict) -> bool:
        """Добавить сделку в БД"""
        try:
            now = datetime.now()

            query = """
                INSERT INTO trades (
                    trade_date, trade_time, pair, trade_type,
                    entry_price, exit_price, position_size,
                    pnl_usd, pnl_pct, category, tags, comment
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
            """

            async with self.pool.acquire() as conn:
                trade_id = await conn.fetchval(
                    query,
                    now.date(),
                    now.time(),
                    trade_data['pair'],
                    trade_data['type'],
                    trade_data['entry'],
                    trade_data['exit'],
                    trade_data.get('size'),
                    trade_data['pnl_usd'],
                    trade_data['pnl_pct'],
                    trade_data['category'],
                    trade_data.get('tags', ''),
                    trade_data.get('comment', '')
                )

                logger.info(f"Trade added with ID: {trade_id}")
                return True

        except Exception as e:
            logger.error(f"Error adding trade: {e}")
            return False

    async def get_trades(self, days: Optional[int] = None) -> pd.DataFrame:
        """Получить сделки за последние N дней"""
        try:
            query = """
                SELECT 
                    id,
                    trade_date as "Дата",
                    trade_time as "Время",
                    pair as "Пара",
                    trade_type as "Тип",
                    entry_price as "Вход",
                    exit_price as "Выход",
                    position_size as "Размер",
                    pnl_usd as "P/L USD",
                    pnl_pct as "P/L %",
                    category as "Категория",
                    tags as "Теги",
                    comment as "Комментарий",
                    created_at
                FROM trades
            """

            if days:
                cutoff_date = datetime.now().date() - timedelta(days=days)
                query += f" WHERE trade_date >= $1 ORDER BY trade_date DESC, trade_time DESC"

                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(query, cutoff_date)
            else:
                query += " ORDER BY trade_date DESC, trade_time DESC"

                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(query)

            # Конвертируем в DataFrame
            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame([dict(row) for row in rows])
            return df

        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return pd.DataFrame()

    async def get_today_stats(self) -> Dict:
        """Статистика за сегодня"""
        try:
            today = datetime.now().date()

            query = """
                SELECT 
                    COUNT(*) as total_count,
                    COALESCE(SUM(pnl_usd), 0) as total_pnl,
                    COUNT(CASE WHEN category = 'стратегия' THEN 1 END) as strategy_count,
                    COUNT(CASE WHEN category = 'импульс' THEN 1 END) as impulse_count
                FROM trades
                WHERE trade_date = $1
            """

            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, today)

            return {
                'count': row['total_count'],
                'pnl': float(row['total_pnl']),
                'strategy_count': row['strategy_count'],
                'impulse_count': row['impulse_count']
            }

        except Exception as e:
            logger.error(f"Error getting today stats: {e}")
            return {
                'count': 0,
                'pnl': 0,
                'strategy_count': 0,
                'impulse_count': 0
            }

    async def get_last_trades(self, limit: int = 10) -> List[Dict]:
        """Получить последние N сделок"""
        try:
            query = """
                SELECT 
                    pair, trade_type, pnl_usd, category, trade_date, trade_time
                FROM trades
                ORDER BY trade_date DESC, trade_time DESC
                LIMIT $1
            """

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, limit)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting last trades: {e}")
            return []

    async def delete_trade(self, trade_id: int) -> bool:
        """Удалить сделку по ID"""
        try:
            query = "DELETE FROM trades WHERE id = $1"

            async with self.pool.acquire() as conn:
                result = await conn.execute(query, trade_id)

            logger.info(f"Trade {trade_id} deleted")
            return True

        except Exception as e:
            logger.error(f"Error deleting trade: {e}")
            return False

    async def get_statistics(self, days: int = 7) -> Dict:
        """Получить расширенную статистику"""
        try:
            cutoff_date = datetime.now().date() - timedelta(days=days)

            query = """
                SELECT 
                    category,
                    COUNT(*) as trades_count,
                    SUM(pnl_usd) as total_pnl,
                    AVG(pnl_usd) as avg_pnl,
                    COUNT(CASE WHEN pnl_usd > 0 THEN 1 END) as winning_trades,
                    COUNT(CASE WHEN pnl_usd < 0 THEN 1 END) as losing_trades,
                    MAX(pnl_usd) as max_win,
                    MIN(pnl_usd) as max_loss
                FROM trades
                WHERE trade_date >= $1
                GROUP BY category
            """

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, cutoff_date)

            stats = {}
            for row in rows:
                stats[row['category']] = dict(row)

            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}