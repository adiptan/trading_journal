import pandas as pd
from typing import Dict, List
from datetime import datetime, timedelta


class TradingAnalytics:

    @staticmethod
    def calculate_metrics(df: pd.DataFrame, category: str = None) -> Dict:
        """Рассчитать метрики для сделок"""
        if df.empty:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0
            }

        if category:
            df = df[df['Категория'] == category]

        winning_trades = df[df['P/L USD'] > 0]
        losing_trades = df[df['P/L USD'] < 0]

        total_wins = winning_trades['P/L USD'].sum() if not winning_trades.empty else 0
        total_losses = abs(losing_trades['P/L USD'].sum()) if not losing_trades.empty else 0

        return {
            'total_trades': len(df),
            'win_rate': len(winning_trades) / len(df) * 100 if len(df) > 0 else 0,
            'total_pnl': df['P/L USD'].sum(),
            'avg_win': winning_trades['P/L USD'].mean() if not winning_trades.empty else 0,
            'avg_loss': losing_trades['P/L USD'].mean() if not losing_trades.empty else 0,
            'profit_factor': total_wins / total_losses if total_losses > 0 else 0
        }

    @staticmethod
    def detect_patterns(df: pd.DataFrame) -> List[str]:
        """Определить паттерны поведения"""
        patterns = []

        if df.empty:
            return patterns

        # Время импульсивных сделок
        impulse_trades = df[df['Категория'] == 'импульс'].copy()
        if not impulse_trades.empty:
            # Конвертируем время в часы
            impulse_trades['Час'] = pd.to_datetime(impulse_trades['Время'], format='%H:%M:%S').dt.hour

            late_night_impulse = impulse_trades[impulse_trades['Час'] >= 22]
            if len(late_night_impulse) > 0:
                pct = len(late_night_impulse) / len(impulse_trades) * 100
                patterns.append(f"⚠️ {pct:.0f}% импульсивных сделок после 22:00")

        # Серии убыточных сделок
        losses_in_row = 0
        max_losses_in_row = 0
        for pnl in df['P/L USD']:
            if pnl < 0:
                losses_in_row += 1
                max_losses_in_row = max(max_losses_in_row, losses_in_row)
            else:
                losses_in_row = 0

        if max_losses_in_row >= 3:
            patterns.append(f"🔴 Максимальная серия убытков: {max_losses_in_row} подряд")

        # Revenge trading detection
        df_sorted = df.sort_values(['Дата', 'Время'])
        revenge_count = 0
        for i in range(1, len(df_sorted)):
            prev_trade = df_sorted.iloc[i - 1]
            curr_trade = df_sorted.iloc[i]

            # Если предыдущая убыточная, а следующая импульсивная
            if prev_trade['P/L USD'] < 0 and curr_trade['Категория'] == 'импульс':
                revenge_count += 1

        if revenge_count > 0:
            patterns.append(f"😤 Обнаружено {revenge_count} попыток отыгрыша после убытка")

        return patterns

    @staticmethod
    def generate_weekly_report(df: pd.DataFrame) -> str:
        """Генерация еженедельного отчёта"""
        if df.empty:
            return "📊 За неделю сделок не было"

        strategy_metrics = TradingAnalytics.calculate_metrics(df, 'стратегия')
        impulse_metrics = TradingAnalytics.calculate_metrics(df, 'импульс')
        total_metrics = TradingAnalytics.calculate_metrics(df)
        patterns = TradingAnalytics.detect_patterns(df)

        report = f"""
📈 <b>НЕДЕЛЬНЫЙ ОТЧЁТ</b>
{'=' * 30}

💰 <b>Общий результат:</b> {total_metrics['total_pnl']:+.2f} USD
📊 Всего сделок: {total_metrics['total_trades']}
📈 Win Rate: {total_metrics['win_rate']:.1f}%

🎯 <b>ПО СТРАТЕГИИ:</b>
   Сделок: {strategy_metrics['total_trades']}
   Win Rate: {strategy_metrics['win_rate']:.1f}%
   P/L: {strategy_metrics['total_pnl']:+.2f} USD
   Средний профит: {strategy_metrics['avg_win']:.2f} USD
   Средний убыток: {strategy_metrics['avg_loss']:.2f} USD

😤 <b>ИМПУЛЬСИВНЫЕ:</b>
   Сделок: {impulse_metrics['total_trades']}
   Win Rate: {impulse_metrics['win_rate']:.1f}%
   P/L: {impulse_metrics['total_pnl']:+.2f} USD
"""

        if patterns:
            report += f"\n🔍 <b>ОБНАРУЖЕННЫЕ ПАТТЕРНЫ:</b>\n"
            for pattern in patterns:
                report += f"   {pattern}\n"

        # Рекомендации
        report += f"\n💡 <b>РЕКОМЕНДАЦИИ:</b>\n"

        if impulse_metrics['total_trades'] > strategy_metrics['total_trades']:
            report += "   ⛔ Импульсивных сделок больше, чем по стратегии!\n"

        if impulse_metrics['total_pnl'] < 0:
            impact = abs(impulse_metrics['total_pnl'])
            report += f"   💸 Импульсивность съела {impact:.2f} USD прибыли\n"

        if strategy_metrics['total_pnl'] > 0 and total_metrics['total_pnl'] < strategy_metrics['total_pnl']:
            report += "   ✅ Стратегия работает! Проблема в дисциплине\n"

        return report