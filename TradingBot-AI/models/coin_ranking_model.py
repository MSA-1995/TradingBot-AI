"""
🏆 Coin Ranking Model
يرتب العملات حسب الأداء ويعطي توصيات
"""

from datetime import datetime, timedelta
import statistics

class CoinRankingModel:
    def __init__(self, storage):
        self.storage = storage
        self.rankings = {}
        self.last_update = None
        print("🏆 Coin Ranking Model initialized")
    
    def analyze_coin_performance(self, symbol):
        """تحليل أداء عملة معينة"""
        try:
            # جلب صفقات العملة
            all_trades = self.storage.get_all_trades()
            coin_trades = [t for t in all_trades if t.get('symbol') == symbol]
            
            if len(coin_trades) < 3:
                return {
                    'symbol': symbol,
                    'rank': 0,
                    'score': 0,
                    'recommendation': 'INSUFFICIENT_DATA',
                    'trades_count': len(coin_trades)
                }
            
            # حساب المقاييس
            wins = [t for t in coin_trades if t.get('profit_percent', 0) > 0]
            losses = [t for t in coin_trades if t.get('profit_percent', 0) < 0]
            
            win_rate = (len(wins) / len(coin_trades)) * 100 if coin_trades else 0
            
            avg_profit = statistics.mean([t['profit_percent'] for t in wins]) if wins else 0
            avg_loss = statistics.mean([abs(t['profit_percent']) for t in losses]) if losses else 0
            
            total_profit = sum(t.get('profit_percent', 0) for t in coin_trades)
            
            # حساب Profit Factor
            total_wins = sum(t['profit_percent'] for t in wins) if wins else 0
            total_losses = abs(sum(t['profit_percent'] for t in losses)) if losses else 1
            profit_factor = total_wins / total_losses if total_losses > 0 else total_wins
            
            # حساب متوسط مدة الصفقة
            avg_duration = statistics.mean([
                t.get('hours_held', 24) for t in coin_trades
            ]) if coin_trades else 24
            
            # حساب الاستقرار (Consistency)
            if len(coin_trades) >= 5:
                profits = [t.get('profit_percent', 0) for t in coin_trades]
                std_dev = statistics.stdev(profits)
                consistency = max(0, 100 - (std_dev * 10))
            else:
                consistency = 50
            
            # حساب النقاط الإجمالية
            score = self._calculate_score(
                win_rate, avg_profit, avg_loss, 
                profit_factor, consistency, len(coin_trades)
            )
            
            # التوصية
            recommendation = self._get_recommendation(score, win_rate, profit_factor)
            
            return {
                'symbol': symbol,
                'score': round(score, 2),
                'win_rate': round(win_rate, 2),
                'avg_profit': round(avg_profit, 2),
                'avg_loss': round(avg_loss, 2),
                'total_profit': round(total_profit, 2),
                'profit_factor': round(profit_factor, 2),
                'consistency': round(consistency, 2),
                'avg_duration_hours': round(avg_duration, 2),
                'trades_count': len(coin_trades),
                'recommendation': recommendation,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"⚠️ Coin analysis error {symbol}: {e}")
            return None
    
    def _calculate_score(self, win_rate, avg_profit, avg_loss, profit_factor, consistency, trades_count):
        """حساب النقاط الإجمالية"""
        score = 0
        
        # Win Rate (0-30 points)
        score += (win_rate / 100) * 30
        
        # Average Profit (0-20 points)
        score += min(avg_profit * 5, 20)
        
        # Profit Factor (0-25 points)
        score += min(profit_factor * 10, 25)
        
        # Consistency (0-15 points)
        score += (consistency / 100) * 15
        
        # Trade Count bonus (0-10 points)
        score += min(trades_count / 2, 10)
        
        return score
    
    def _get_recommendation(self, score, win_rate, profit_factor):
        """الحصول على التوصية"""
        if score >= 80 and win_rate >= 75:
            return 'STRONG_BUY'
        elif score >= 65 and win_rate >= 65:
            return 'BUY'
        elif score >= 50 and win_rate >= 55:
            return 'HOLD'
        elif score >= 35:
            return 'WATCH'
        else:
            return 'AVOID'
    
    def rank_all_coins(self, symbols):
        """ترتيب جميع العملات"""
        try:
            rankings = []
            
            for symbol in symbols:
                analysis = self.analyze_coin_performance(symbol)
                if analysis and analysis['trades_count'] >= 3:
                    rankings.append(analysis)
            
            # ترتيب حسب النقاط
            rankings.sort(key=lambda x: x['score'], reverse=True)
            
            # إضافة الترتيب
            for i, coin in enumerate(rankings, 1):
                coin['rank'] = i
            
            self.rankings = {coin['symbol']: coin for coin in rankings}
            self.last_update = datetime.now()
            
            return rankings
            
        except Exception as e:
            print(f"⚠️ Ranking error: {e}")
            return []
    
    def get_top_coins(self, limit=5):
        """الحصول على أفضل العملات"""
        if not self.rankings:
            return []
        
        sorted_coins = sorted(
            self.rankings.values(), 
            key=lambda x: x['score'], 
            reverse=True
        )
        
        return sorted_coins[:limit]
    
    def get_worst_coins(self, limit=5):
        """الحصول على أسوأ العملات"""
        if not self.rankings:
            return []
        
        sorted_coins = sorted(
            self.rankings.values(), 
            key=lambda x: x['score']
        )
        
        return sorted_coins[:limit]
    
    def should_trade_coin(self, symbol):
        """هل يجب التداول في هذه العملة؟"""
        if symbol not in self.rankings:
            return {'trade': True, 'reason': 'No history', 'confidence_adjustment': 0}
        
        coin = self.rankings[symbol]
        
        if coin['recommendation'] == 'STRONG_BUY':
            return {
                'trade': True, 
                'reason': 'Top performer',
                'confidence_adjustment': +10
            }
        elif coin['recommendation'] == 'BUY':
            return {
                'trade': True,
                'reason': 'Good performer',
                'confidence_adjustment': +5
            }
        elif coin['recommendation'] == 'HOLD':
            return {
                'trade': True,
                'reason': 'Average performer',
                'confidence_adjustment': 0
            }
        elif coin['recommendation'] == 'WATCH':
            return {
                'trade': True,
                'reason': 'Below average',
                'confidence_adjustment': -5
            }
        else:  # AVOID
            return {
                'trade': False,
                'reason': 'Poor performer',
                'confidence_adjustment': -15
            }
    
    def get_coin_stats(self, symbol):
        """الحصول على إحصائيات العملة"""
        if symbol in self.rankings:
            return self.rankings[symbol]
        return None
    
    def get_ranking_report(self):
        """تقرير شامل للترتيب"""
        if not self.rankings:
            return None
        
        total_coins = len(self.rankings)
        strong_buy = sum(1 for c in self.rankings.values() if c['recommendation'] == 'STRONG_BUY')
        buy = sum(1 for c in self.rankings.values() if c['recommendation'] == 'BUY')
        avoid = sum(1 for c in self.rankings.values() if c['recommendation'] == 'AVOID')
        
        avg_win_rate = statistics.mean([c['win_rate'] for c in self.rankings.values()])
        avg_score = statistics.mean([c['score'] for c in self.rankings.values()])
        
        return {
            'total_coins': total_coins,
            'strong_buy_count': strong_buy,
            'buy_count': buy,
            'avoid_count': avoid,
            'avg_win_rate': round(avg_win_rate, 2),
            'avg_score': round(avg_score, 2),
            'last_update': self.last_update.isoformat() if self.last_update else None
        }
