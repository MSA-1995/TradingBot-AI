"""
📊 Self-Analysis Dashboard - لوحة التحليل الذاتي
يحلل أداء البوت ويعطي توصيات للتحسين
"""
from datetime import datetime, timedelta
import json

class SelfAnalysisDashboard:
    """
    يحلل:
    - معدل النجاح لكل عملة
    - أفضل وأسوأ أوقات التداول
    - الأخطاء المتكررة
    - نقاط القوة والضعف
    """
    
    def __init__(self, storage):
        self.storage = storage
    
    def generate_performance_report(self, days=7):
        """
        تقرير أداء شامل
        """
        trades = self.storage.get_all_trades()
        if not trades:
            return {"error": "No trades found"}
        
        # فلترة الصفقات حسب الفترة
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_trades = [t for t in trades if self._parse_date(t.get('timestamp')) >= cutoff_date]
        
        if not recent_trades:
            return {"error": f"No trades in last {days} days"}
        
        # 1. الإحصائيات العامة
        total_trades = len(recent_trades)
        winning_trades = [t for t in recent_trades if t.get('profit', 0) > 0]
        losing_trades = [t for t in recent_trades if t.get('profit', 0) <= 0]
        
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        total_profit = sum(t.get('profit', 0) for t in recent_trades)
        avg_profit = total_profit / total_trades if total_trades > 0 else 0
        
        best_trade = max(recent_trades, key=lambda t: t.get('profit', 0))
        worst_trade = min(recent_trades, key=lambda t: t.get('profit', 0))
        
        # 2. تحليل العملات
        symbol_performance = {}
        for trade in recent_trades:
            symbol = trade.get('symbol')
            if symbol not in symbol_performance:
                symbol_performance[symbol] = {'wins': 0, 'losses': 0, 'total_profit': 0}
            
            if trade.get('profit', 0) > 0:
                symbol_performance[symbol]['wins'] += 1
            else:
                symbol_performance[symbol]['losses'] += 1
            
            symbol_performance[symbol]['total_profit'] += trade.get('profit', 0)
        
        # ترتيب العملات حسب الأداء
        best_symbols = sorted(symbol_performance.items(), 
                            key=lambda x: x[1]['total_profit'], 
                            reverse=True)[:3]
        worst_symbols = sorted(symbol_performance.items(), 
                             key=lambda x: x[1]['total_profit'])[:3]
        
        # 3. تحليل الأوقات
        hourly_performance = {}
        for trade in recent_trades:
            timestamp = self._parse_date(trade.get('timestamp'))
            if timestamp:
                hour = timestamp.hour
                if hour not in hourly_performance:
                    hourly_performance[hour] = {'wins': 0, 'losses': 0, 'total_profit': 0}
                
                if trade.get('profit', 0) > 0:
                    hourly_performance[hour]['wins'] += 1
                else:
                    hourly_performance[hour]['losses'] += 1
                
                hourly_performance[hour]['total_profit'] += trade.get('profit', 0)
        
        best_hours = sorted(hourly_performance.items(), 
                          key=lambda x: x[1]['total_profit'], 
                          reverse=True)[:3]
        worst_hours = sorted(hourly_performance.items(), 
                           key=lambda x: x[1]['total_profit'])[:3]
        
        # 4. تحليل الأخطاء
        trap_trades = [t for t in recent_trades if t.get('trade_quality') in ['TRAP', 'RISKY']]
        trap_rate = (len(trap_trades) / total_trades * 100) if total_trades > 0 else 0
        
        # 5. التوصيات
        recommendations = self._generate_recommendations(
            win_rate, trap_rate, best_symbols, worst_symbols, best_hours, worst_hours
        )
        
        return {
            'period': f'Last {days} days',
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_trades': total_trades,
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': round(win_rate, 2),
                'total_profit': round(total_profit, 2),
                'avg_profit_per_trade': round(avg_profit, 2),
                'trap_rate': round(trap_rate, 2)
            },
            'best_trade': {
                'symbol': best_trade.get('symbol'),
                'profit': round(best_trade.get('profit', 0), 2),
                'timestamp': str(best_trade.get('timestamp'))
            },
            'worst_trade': {
                'symbol': worst_trade.get('symbol'),
                'profit': round(worst_trade.get('profit', 0), 2),
                'timestamp': str(worst_trade.get('timestamp'))
            },
            'top_symbols': [
                {
                    'symbol': s[0],
                    'wins': s[1]['wins'],
                    'losses': s[1]['losses'],
                    'total_profit': round(s[1]['total_profit'], 2),
                    'win_rate': round(s[1]['wins'] / (s[1]['wins'] + s[1]['losses']) * 100, 1)
                }
                for s in best_symbols
            ],
            'worst_symbols': [
                {
                    'symbol': s[0],
                    'wins': s[1]['wins'],
                    'losses': s[1]['losses'],
                    'total_profit': round(s[1]['total_profit'], 2)
                }
                for s in worst_symbols
            ],
            'best_hours': [
                {
                    'hour': f"{h[0]:02d}:00",
                    'wins': h[1]['wins'],
                    'losses': h[1]['losses'],
                    'total_profit': round(h[1]['total_profit'], 2)
                }
                for h in best_hours
            ],
            'worst_hours': [
                {
                    'hour': f"{h[0]:02d}:00",
                    'wins': h[1]['wins'],
                    'losses': h[1]['losses'],
                    'total_profit': round(h[1]['total_profit'], 2)
                }
                for h in worst_hours
            ],
            'recommendations': recommendations
        }
    
    def _parse_date(self, timestamp):
        """تحويل timestamp لـ datetime"""
        if isinstance(timestamp, datetime):
            return timestamp
        try:
            return datetime.fromisoformat(str(timestamp))
        except:
            return None
    
    def _generate_recommendations(self, win_rate, trap_rate, best_symbols, worst_symbols, best_hours, worst_hours):
        """توليد توصيات ذكية"""
        recommendations = []
        
        # 1. توصيات معدل النجاح
        if win_rate < 50:
            recommendations.append({
                'type': 'CRITICAL',
                'title': 'معدل نجاح منخفض',
                'message': f'معدل النجاح {win_rate:.1f}% - يجب رفع حد الثقة أو تقليل عدد الصفقات',
                'action': 'زيادة MIN_CONFIDENCE من 75 إلى 85'
            })
        elif win_rate > 75:
            recommendations.append({
                'type': 'SUCCESS',
                'title': 'أداء ممتاز',
                'message': f'معدل نجاح {win_rate:.1f}% - يمكن زيادة عدد الصفقات',
                'action': 'تقليل MIN_CONFIDENCE قليلاً لزيادة الفرص'
            })
        
        # 2. توصيات الفخاخ
        if trap_rate > 20:
            recommendations.append({
                'type': 'WARNING',
                'title': 'نسبة فخاخ عالية',
                'message': f'{trap_rate:.1f}% من الصفقات فخاخ - تحسين كشف الفخاخ مطلوب',
                'action': 'تفعيل Liquidation Shield'
            })
        
        # 3. توصيات العملات
        if worst_symbols:
            worst_symbol = worst_symbols[0][0]
            recommendations.append({
                'type': 'INFO',
                'title': 'عملة ضعيفة الأداء',
                'message': f'{worst_symbol} تسبب خسائر متكررة',
                'action': f'تجنب {worst_symbol} مؤقتاً أو رفع حد الثقة لها'
            })
        
        # 4. توصيات الأوقات
        if worst_hours:
            worst_hour = worst_hours[0][0]
            recommendations.append({
                'type': 'INFO',
                'title': 'وقت ضعيف الأداء',
                'message': f'الساعة {worst_hour:02d}:00 تشهد خسائر متكررة',
                'action': f'تجنب التداول في الساعة {worst_hour:02d}:00'
            })
        
        return recommendations
    
    def send_report_to_discord(self, report, webhook_url):
        """إرسال التقرير لديسكورد بشكل جميل"""
        try:
            import requests
            
            if 'error' in report:
                return False
            
            summary = report['summary']
            
            # تحديد اللون بناءً على الأداء
            if summary['win_rate'] >= 70:
                color = 0x00ff00  # أخضر
            elif summary['win_rate'] >= 50:
                color = 0xffff00  # أصفر
            else:
                color = 0xff0000  # أحمر
            
            # بناء الـ Embed - نفس أسلوب Portfolio Report
            embed = {
                "title": f"PERFORMANCE REPORT - {report['period']}",
                "color": color,
                "fields": [
                    {
                        "name": "Total Trades",
                        "value": f"{summary['total_trades']}",
                        "inline": True
                    },
                    {
                        "name": "Win Rate",
                        "value": f"{summary['win_rate']:.1f}%",
                        "inline": True
                    },
                    {
                        "name": "Total Profit",
                        "value": f"{summary['total_profit']:+.2f}%",
                        "inline": True
                    },
                    {
                        "name": "Average Profit",
                        "value": f"{summary['avg_profit_per_trade']:+.2f}%",
                        "inline": True
                    },
                    {
                        "name": "Trap Rate",
                        "value": f"{summary['trap_rate']:.1f}%",
                        "inline": True
                    },
                    {
                        "name": "Winning Trades",
                        "value": f"{summary['winning_trades']}",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "MSA Trading Bot • Self-Analysis System"
                },
                "timestamp": report['generated_at']
            }
            
            # أفضل وأسوأ صفقة
            best = report['best_trade']
            worst = report['worst_trade']
            embed['fields'].append({
                "name": "Best Trade",
                "value": f"{best['symbol']}: {best['profit']:+.2f}%",
                "inline": True
            })
            embed['fields'].append({
                "name": "Worst Trade",
                "value": f"{worst['symbol']}: {worst['profit']:+.2f}%",
                "inline": True
            })
            
            # أفضل العملات
            if report['top_symbols']:
                top_text = "\n".join([
                    f"**{s['symbol']}**\nProfit: {s['total_profit']:+.2f}% | Win Rate: {s['win_rate']:.0f}%\n"
                    for s in report['top_symbols'][:3]
                ])
                embed['fields'].append({
                    "name": "Top Performing Symbols",
                    "value": top_text.strip() or "No data available",
                    "inline": False
                })
            
            # أفضل الأوقات
            if report['best_hours']:
                hours_text = "\n".join([
                    f"**{h['hour']}**\nProfit: {h['total_profit']:+.2f}% | Trades: {h['wins'] + h['losses']}\n"
                    for h in report['best_hours'][:3]
                ])
                embed['fields'].append({
                    "name": "Best Trading Hours",
                    "value": hours_text.strip() or "No data available",
                    "inline": False
                })
            
            # التوصيات
            if report['recommendations']:
                rec_text = "\n".join([
                    f"**{r['title']}**\n{r['message']}\n"
                    for r in report['recommendations'][:3]
                ])
                if rec_text:
                    embed['fields'].append({
                        "name": "Recommendations",
                        "value": rec_text.strip(),
                        "inline": False
                    })
            
            # إرسال للديسكورد
            response = requests.post(
                webhook_url,
                json={"embeds": [embed]},
                timeout=10
            )
            
            return response.status_code == 204
            
        except Exception as e:
            print(f"❌ Error sending report to Discord: {e}")
            return False
