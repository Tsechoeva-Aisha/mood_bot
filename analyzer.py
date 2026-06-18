import matplotlib
matplotlib.use('Agg') 

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class Analyzer:
    """Анализатор данных для построения графиков и статистики"""
    
    @staticmethod
    def _prepare_dataframe(records):
        """Подготавливает DataFrame из записей"""
        if not records:
            return None
        
        try:
           
            if isinstance(records, list) and len(records) > 0:
                if isinstance(records[0], dict):
                    df = pd.DataFrame(records)
                    
                    if 'record_date' in df.columns:
                        df = df.rename(columns={'record_date': 'date'})
                else:
                    df = pd.DataFrame(records, columns=['date', 'mood', 'work_hours', 'sleep_hours', 'comment'])
            else:
                return None
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            return df
        except Exception as e:
            logger.error(f"Ошибка подготовки DataFrame: {e}")
            return None

    @staticmethod
    def generate_mood_plot(records, period_days=30):
        """Генерирует линейный график настроения, сна и работы за период"""
        df = Analyzer._prepare_dataframe(records)
        if df is None or df.empty:
            return None
        
        end_date = df['date'].max()
        start_date = end_date - pd.Timedelta(days=period_days)
        df = df[df['date'] >= start_date]
        
        if df.empty:
            return None
        
        try:
            plt.style.use('seaborn-v0_8-darkgrid')
        except:
            plt.style.use('default')
        
        fig, ax1 = plt.subplots(figsize=(12, 6))
        
        ax1.plot(df['date'], df['mood'], 'o-', color='royalblue', linewidth=2, 
                markersize=6, label='Настроение (1-5)')
        ax1.set_xlabel('Дата', fontsize=11)
        ax1.set_ylabel('Настроение', color='royalblue', fontsize=11)
        ax1.tick_params(axis='y', labelcolor='royalblue')
        ax1.set_ylim(0.5, 5.5)
        
        if len(df) > 3:
            try:
                x = np.arange(len(df))
                z = np.polyfit(x, df['mood'].values, 1)
                p = np.poly1d(z)
                ax1.plot(df['date'], p(x), "b--", alpha=0.5, 
                        label='Тренд настроения', linewidth=1.5)
            except:
                pass
        
        ax2 = ax1.twinx()
        ax2.plot(df['date'], df['work_hours'], 's--', color='orange', 
                linewidth=1.5, markersize=5, label='Работа/учеба (ч)')
        ax2.plot(df['date'], df['sleep_hours'], 'd--', color='green', 
                linewidth=1.5, markersize=5, label='Сон (ч)')
        ax2.set_ylabel('Часы', color='black', fontsize=11)
        ax2.tick_params(axis='y', labelcolor='black')
        
        ax1.grid(True, alpha=0.3, linestyle='--')
        plt.xticks(rotation=45, ha='right')
        
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', framealpha=0.9)
        
        
        avg_mood = df['mood'].mean()
        plt.title(f'Динамика настроения, работы и сна (последние {len(df)} дней)\n'
                 f'Среднее настроение: {avg_mood:.1f}/5', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf

    @staticmethod
    def format_weekly_stats(records):
        """Форматирует статистику за неделю в текст"""
        if not records:
            return "Нет данных за последнюю неделю."
        
        try:
            df = Analyzer._prepare_dataframe(records)
            if df is None or df.empty:
                return "Нет данных."
            
            df = df.tail(7)
            
            if df.empty:
                return "Нет данных за последнюю неделю."
            
            avg_mood = df['mood'].mean()
            avg_work = df['work_hours'].mean()
            avg_sleep = df['sleep_hours'].mean()
            
            best_day = df.loc[df['mood'].idxmax()]
            worst_day = df.loc[df['mood'].idxmin()]
            
            text = f"📊 **Статистика за неделю (последние {len(df)} дней)**\n"
            text += "=" * 35 + "\n\n"
            text += f"😊 Среднее настроение: {avg_mood:.1f}/5\n"
            text += f"💼 Средняя работа/учеба: {avg_work:.1f} ч\n"
            text += f"😴 Средний сон: {avg_sleep:.1f} ч\n\n"
            
            text += f"🌟 **Лучший день:** {best_day['date'].strftime('%d.%m (%a)')}\n"
            text += f"   Настроение: {best_day['mood']}/5, Работа: {best_day['work_hours']:.1f}ч, Сон: {best_day['sleep_hours']:.1f}ч\n"
            if pd.notna(best_day.get('comment')):
                text += f"   Комментарий: {best_day['comment'][:50]}\n"
            
            text += f"\n😔 **Худший день:** {worst_day['date'].strftime('%d.%m (%a)')}\n"
            text += f"   Настроение: {worst_day['mood']}/5, Работа: {worst_day['work_hours']:.1f}ч, Сон: {worst_day['sleep_hours']:.1f}ч\n"
            if pd.notna(worst_day.get('comment')):
                text += f"   Комментарий: {worst_day['comment'][:50]}\n"
            
            text += "\n**📅 По дням:**\n"
            text += "-" * 35 + "\n"
            for _, row in df.iterrows():
                date_str = row['date'].strftime('%d.%m (%a)')
                mood_val = int(row['mood'])
                mood_emoji = ['😢', '😕', '😐', '🙂', '😊'][mood_val-1] if 1 <= mood_val <= 5 else '❓'
                text += f"{date_str}: {mood_emoji} {row['mood']}/5 | 💼 {row['work_hours']:.1f}ч | 😴 {row['sleep_hours']:.1f}ч\n"
            
            return text
        except Exception as e:
            logger.error(f"Ошибка форматирования статистики: {e}")
            return f"❌ Ошибка при обработке данных: {e}"

    @staticmethod
    def format_monthly_stats(records):
        """Форматирует статистику за месяц"""
        if not records:
            return "Нет данных за последний месяц."
        
        try:
            df = Analyzer._prepare_dataframe(records)
            if df is None or df.empty:
                return "Нет данных."
            
            avg_mood = df['mood'].mean()
            avg_work = df['work_hours'].mean()
            avg_sleep = df['sleep_hours'].mean()
            
            df['week'] = df['date'].dt.isocalendar().week
            weekly_stats = df.groupby('week').agg({
                'mood': 'mean',
                'work_hours': 'mean',
                'sleep_hours': 'mean'
            }).round(1)
            
            text = f"📅 **Статистика за месяц (всего {len(df)} записей)**\n"
            text += "=" * 35 + "\n\n"
            text += f"😊 Среднее настроение: {avg_mood:.1f}/5\n"
            text += f"💼 Средняя работа/учеба: {avg_work:.1f} ч\n"
            text += f"😴 Средний сон: {avg_sleep:.1f} ч\n\n"
            
            text += "**📈 Динамика по неделям:**\n"
            for week, stats in weekly_stats.iterrows():
                text += f"  Неделя {week}: настроение {stats['mood']}/5, работа {stats['work_hours']}ч, сон {stats['sleep_hours']}ч\n"
            
            return text
        except Exception as e:
            logger.error(f"Ошибка форматирования статистики: {e}")
            return f"❌ Ошибка при обработке данных: {e}"

    @staticmethod
    def format_insights(db, user_id):
        """Генерирует инсайты на основе данных из БД"""
        try:
            overall, sleep_impact, work_impact = db.get_stats_for_insights(user_id)
        except Exception as e:
            logger.error(f"Ошибка получения инсайтов: {e}")
            return "❌ Ошибка получения данных для анализа."
        
        if not overall or overall['avg_mood'] is None:
            return "📭 Недостаточно данных для анализа. Добавьте хотя бы несколько записей."
        
        text = "🔍 **Ваши персональные инсайты**\n"
        text += "=" * 35 + "\n\n"
        
        text += f"📊 **Общая статистика:**\n"
        text += f"  • Настроение: {overall['avg_mood']:.1f}/5 "
        if overall['avg_mood'] >= 4:
            text += "👍 Отлично!\n"
        elif overall['avg_mood'] >= 3:
            text += "👌 Неплохо\n"
        else:
            text += "😟 Требует внимания\n"
        
        text += f"  • Продуктивность: {overall['avg_work']:.1f} ч/день\n"
        text += f"  • Сон: {overall['avg_sleep']:.1f} ч/ночь "
        if overall['avg_sleep'] >= 8:
            text += "💪 Отлично!\n"
        elif overall['avg_sleep'] >= 7:
            text += "✅ Хорошо\n"
        else:
            text += "⚠️ Мало\n"
        
        text += "\n🎯 **Рекомендации:**\n"
        
        recommendations = []
        if overall['avg_sleep'] and overall['avg_sleep'] < 7:
            recommendations.append("  • 😴 Старайтесь спать 7-8 часов — это ключ к хорошему настроению")
        
        if overall['avg_mood'] and overall['avg_mood'] < 3:
            recommendations.append("  • 🧘 Найдите время для отдыха и приятных занятий")
        
        if overall['avg_work'] and overall['avg_work'] < 2:
            recommendations.append("  • 📋 Разбивайте задачи на маленькие шаги для повышения продуктивности")
        
        if not recommendations:
            recommendations.append("  • ✨ Продолжайте в том же духе! У вас отличный баланс")
            recommendations.append("  • 📈 Отслеживайте динамику, чтобы сохранять результаты")
        
        text += "\n".join(recommendations)
        
        return text