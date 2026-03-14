"""
🔍 Simple Coin Scanner - Top 20 Popular Coins
Fast and reliable analysis of 20 most popular cryptocurrencies
"""

import time
import gc
from datetime import datetime
from colorama import Fore, Style

class CoinScanner:
    def __init__(self, exchange, ai_brain=None, mtf_analyzer=None, risk_manager=None):
        self.exchange = exchange
        self.ai_brain = ai_brain
        self.mtf_analyzer = mtf_analyzer
        self.risk_manager = risk_manager
        
        # قائمة العملات المشهورة (20 عملة)
        self.popular_coins = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT',
            'MATIC/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT', 'UNI/USDT',
            'ATOM/USDT', 'ALGO/USDT', 'XRP/USDT', 'LTC/USDT', 'BCH/USDT',
            'ETC/USDT', 'FIL/USDT', 'AAVE/USDT', 'SUSHI/USDT', 'COMP/USDT'
        ]
        
        self.top_coins = []  # النتائج
        self.last_scan = None
    
    def scan_coins(self):
        """فحص العملات المشهورة (20 عملة)"""
        start_time = time.time()
        
        try:
            print(f"🔍 Scanning 20 popular coins...")
            
            all_scores = {}
            
            # تحليل كل عملة من القائمة المشهورة
            for i, symbol in enumerate(self.popular_coins, 1):
                try:
                    print(f"   Active: {i}/20 - {symbol}", end="\r")
                    score = self._analyze_coin_quick(symbol)
                    if score > 0:
                        all_scores[symbol] = score
                except Exception as e:
                    continue
            
            # ترتيب حسب Score
            sorted_coins = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
            
            # تحليل ذكي للأفضل (إذا متوفر AI)
            if self.ai_brain or self.mtf_analyzer:
                ai_scores = {}
                for symbol, base_score in sorted_coins:
                    try:
                        ai_score = self._analyze_coin_with_ai(symbol, base_score)
                        if ai_score > 0:
                            ai_scores[symbol] = ai_score
                    except:
                        ai_scores[symbol] = base_score
                
                # ترتيب حسب AI Score
                sorted_ai = sorted(ai_scores.items(), key=lambda x: x[1], reverse=True)
                self.top_coins = sorted_ai
            else:
                self.top_coins = sorted_coins
            
            self.last_scan = datetime.now()
            
            elapsed = time.time() - start_time
            print(f"\n✅ Scan completed in {elapsed:.1f}s - Found {len(self.top_coins)} coins")
            
            # تنظيف الذاكرة
            gc.collect()
            
        except Exception as e:
            print(f"❌ Scan error: {e}")

    
    def _analyze_coin_quick(self, symbol):
        """تحليل سريع للعملة"""
        try:
            # جلب OHLCV (آخر 100 شمعة - 5 دقائق)
            ohlcv = self.exchange.fetch_ohlcv(symbol, '5m', limit=100)
            
            if not ohlcv or len(ohlcv) < 50:
                return 0
            
            import pandas as pd
            import ta
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # حساب المؤشرات
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
            
            macd = ta.trend.MACD(df['close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_diff'] = macd.macd_diff()
            
            # Volume ratio
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            
            # آخر قيم
            last_rsi = df['rsi'].iloc[-1]
            last_macd_diff = df['macd_diff'].iloc[-1]
            last_volume = df['volume'].iloc[-1]
            last_volume_sma = df['volume_sma'].iloc[-1]
            
            # حماية من None/NaN
            if pd.isna(last_rsi) or pd.isna(last_macd_diff) or pd.isna(last_volume_sma):
                return 0
            
            volume_ratio = last_volume / last_volume_sma if last_volume_sma > 0 else 0
            
            # حساب Score (0-100)
            score = 0
            
            # RSI (0-40)
            if last_rsi < 25:
                score += 40
            elif last_rsi < 30:
                score += 35
            elif last_rsi < 35:
                score += 30
            elif last_rsi < 40:
                score += 20
            elif last_rsi < 45:
                score += 10
            
            # MACD (0-30)
            if last_macd_diff > 0:
                if last_macd_diff > 20:
                    score += 30
                elif last_macd_diff > 10:
                    score += 20
                else:
                    score += 10
            
            # Volume (0-30)
            if volume_ratio > 2.5:
                score += 30
            elif volume_ratio > 2.0:
                score += 25
            elif volume_ratio > 1.5:
                score += 20
            elif volume_ratio > 1.2:
                score += 15
            elif volume_ratio > 1.0:
                score += 10
            
            # تنظيف
            del df
            gc.collect()
            
            return score
        
        except Exception as e:
            return 0
    
    def _analyze_coin_with_ai(self, symbol, base_score):
        """تحليل ذكي متقدم للعملة"""
        try:
            # جلب البيانات
            from analysis import get_market_analysis, get_multi_timeframe_analysis
            
            analysis = get_market_analysis(self.exchange, symbol)
            if not analysis:
                return base_score
            
            mtf = get_multi_timeframe_analysis(self.exchange, symbol)
            if not mtf:
                return base_score
            
            # حساب price drop
            price_drop = {'drop_percent': 0, 'confirmed': False}
            try:
                df = analysis['df']
                if len(df) >= 12:
                    import pandas as pd
                    highest_price_1h = df['high'].tail(12).max()
                    current_price_df = df['close'].iloc[-1]
                    
                    if highest_price_1h is not None and current_price_df is not None and highest_price_1h > 0:
                        if not pd.isna(highest_price_1h) and not pd.isna(current_price_df):
                            drop_percent = ((highest_price_1h - current_price_df) / highest_price_1h) * 100
                            price_drop = {
                                'drop_percent': drop_percent,
                                'highest_1h': highest_price_1h,
                                'current': current_price_df,
                                'confirmed': drop_percent >= 2.0
                            }
            except:
                pass
            
            ai_score = base_score
            
            # 1. AI Brain Analysis
            if self.ai_brain:
                try:
                    decision = self.ai_brain.should_buy(symbol, analysis, mtf, price_drop)
                    
                    if decision['action'] == 'BUY':
                        # إضافة نقاط من AI
                        ai_confidence = decision.get('confidence', 0)
                        if ai_confidence >= 70:
                            ai_score += 30
                        elif ai_confidence >= 65:
                            ai_score += 20
                        elif ai_confidence >= 60:
                            ai_score += 10
                    elif decision['action'] == 'SKIP':
                        # تقليل النقاط
                        ai_score -= 20
                except:
                    pass
            
            # 2. Multi-Timeframe Analysis
            if self.mtf_analyzer:
                try:
                    mtf_analysis = self.mtf_analyzer.analyze(symbol)
                    if mtf_analysis:
                        mtf_boost = mtf_analysis.get('confidence_boost', 0) or 0
                        ai_score += mtf_boost
                        
                        entry_point = self.mtf_analyzer.get_best_entry_point(symbol)
                        if entry_point:
                            if entry_point.get('entry') == 'EXCELLENT':
                                ai_score += 15
                            elif entry_point.get('entry') == 'GOOD':
                                ai_score += 10
                except:
                    pass
            
            # 3. Risk Manager - Win Rate Check
            if self.risk_manager:
                try:
                    from storage import StorageManager
                    storage = StorageManager()
                    all_trades = storage.get_all_trades()
                    
                    coin_trades = [t for t in all_trades if t.get('symbol') == symbol]
                    
                    if len(coin_trades) >= 3:
                        wins = sum(1 for t in coin_trades if t.get('profit_percent', 0) > 0)
                        win_rate = (wins / len(coin_trades)) * 100
                        
                        if win_rate > 75:
                            ai_score += 20
                        elif win_rate > 65:
                            ai_score += 10
                        elif win_rate < 40:
                            ai_score -= 20
                except:
                    pass
            
            # تنظيف
            del analysis
            del mtf
            gc.collect()
            
            return max(0, ai_score)
        
        except Exception as e:
            return base_score
    
    def get_top_coins(self):
        """الحصول على القائمة الحالية"""
        return self.top_coins.copy()
    
    def get_scan_status(self):
        """حالة الفحص"""
        return {
            'last_scan': self.last_scan,
            'top_coins_count': len(self.top_coins)
        }
