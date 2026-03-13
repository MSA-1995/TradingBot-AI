"""
🔍 Dynamic Coin Scanner - 3 Levels System
Level 1: Quick Scanner (every 1 minute) - Hot opportunities
Level 2: Deep Scanner (every 30 minutes) - Full analysis
Level 3: Main Loop (every 10 seconds) - Trading
"""

import threading
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
        self.top_coins = []  # القائمة الديناميكية
        self.hot_opportunities = []  # الفرص السريعة
        self.coins_lock = threading.Lock()
        self.last_deep_scan = None
        self.last_quick_scan = None
        
        print("🔍 Dynamic Coin Scanner initialized")
        print("   Level 1: Quick scan every 1 minute")
        print("   Level 2: Deep scan every 30 minutes")
        if ai_brain:
            print("   🧠 AI Brain: ACTIVE for deep analysis")
    
    def start(self):
        """تشغيل الـThreads"""
        # Thread 1: Quick Scanner
        quick_thread = threading.Thread(target=self._quick_scanner_loop, daemon=True)
        quick_thread.start()
        
        # Thread 2: Deep Scanner
        deep_thread = threading.Thread(target=self._deep_scanner_loop, daemon=True)
        deep_thread.start()
        
        print("✅ Coin Scanner threads started!")
    
    def _quick_scanner_loop(self):
        """Quick Scanner - كل دقيقة"""
        while True:
            try:
                self._quick_scan()
                time.sleep(60)  # دقيقة واحدة
            except Exception as e:
                print(f"⚠️ Quick scanner error: {e}")
                time.sleep(60)
    
    def _deep_scanner_loop(self):
        """Deep Scanner - كل 60 دقيقة (مسرع)"""
        # فحص أولي فوري
        try:
            self._deep_scan()
        except Exception as e:
            print(f"⚠️ Initial deep scan error: {e}")
        
        while True:
            try:
                time.sleep(3600)  # 60 دقيقة بدل 30
                self._deep_scan()
            except Exception as e:
                print(f"⚠️ Deep scanner error: {e}")
                time.sleep(3600)
    
    def _quick_scan(self):
        """فحص سريع للفرص الساخنة"""
        try:
            # جلب tickers (طلب واحد فقط - خفيف جداً!)
            tickers = self.exchange.fetch_tickers()
            
            hot_coins = []
            
            for symbol, ticker in tickers.items():
                # فقط USDT pairs
                if not symbol.endswith('/USDT'):
                    continue
                
                # تجاهل Stablecoins
                if any(stable in symbol for stable in ['USDT/', 'USDC/', 'BUSD/', 'DAI/']):
                    continue
                
                try:
                    volume_24h = ticker.get('quoteVolume', 0) or 0
                    price_change = ticker.get('percentage', 0) or 0
                    last_price = ticker.get('last', 0) or 0
                    
                    # شروط الفرصة الساخنة (مخففة لـTestnet):
                    # 1. Volume عالي (> $500K)
                    # 2. انخفاض قوي (-2% إلى -8%)
                    # 3. سعر معقول (> $0.001)
                    if volume_24h > 500_000:  # كان $5M
                        if -8 < price_change < -2:
                            if last_price > 0.001:  # كان $0.01
                                hot_coins.append({
                                    'symbol': symbol,
                                    'volume': volume_24h,
                                    'change': price_change,
                                    'price': last_price,
                                    'score': self._calculate_hot_score(volume_24h, price_change)
                                })
                except:
                    continue
            
            # ترتيب حسب Score
            hot_coins.sort(key=lambda x: x['score'], reverse=True)
            
            # حفظ أفضل 5 فرص
            with self.coins_lock:
                self.hot_opportunities = hot_coins[:5]
                self.last_quick_scan = datetime.now()
            
            if hot_coins:
                # طباعة صامتة - بدون عرض
                pass
        
        except Exception as e:
            print(f"⚠️ Quick scan error: {e}")
    
    def _deep_scan(self):
        """فحص عميق شامل"""
        print(f"\n{'='*60}")
        print(f"🔍 Deep Scan Started - Analyzing 995 coins...")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            # المرحلة 1: فلترة سريعة
            print("📊 Phase 1: Quick filtering...")
            tickers = self.exchange.fetch_tickers()
            
            filtered_coins = []
            for symbol, ticker in tickers.items():
                if not symbol.endswith('/USDT'):
                    continue
                
                if any(stable in symbol for stable in ['USDT/', 'USDC/', 'BUSD/', 'DAI/']):
                    continue
                
                try:
                    volume_24h = ticker.get('quoteVolume', 0) or 0
                    last_price = ticker.get('last', 0) or 0
                    
                    # فلترة أولية (مخففة لـTestnet)
                    if volume_24h > 100_000:  # Volume > $100K (كان $1M)
                        if last_price > 0.001:  # Price > $0.001 (كان $0.01)
                            filtered_coins.append(symbol)
                except:
                    continue
            
            print(f"   ✅ Filtered: {len(filtered_coins)} coins (from 995)")
            
            # المرحلة 2: تحليل بـBatch
            print("🧠 Phase 2: Deep analysis...")
            
            all_scores = {}
            batch_size = 50
            
            for i in range(0, len(filtered_coins), batch_size):
                batch = filtered_coins[i:i+batch_size]
                
                for symbol in batch:
                    try:
                        score = self._analyze_coin_quick(symbol)
                        if score > 0:
                            all_scores[symbol] = score
                    except:
                        continue
                
                # تنظيف الذاكرة
                gc.collect()
                
                # طباعة التقدم بهدوء (كل 50 عملة)
                if (i + batch_size) % 250 == 0:  # كل 250 عملة بدل كل 50
                    progress = min(i + batch_size, len(filtered_coins))
                    print(f"   Progress: {progress}/{len(filtered_coins)} coins analyzed...")
            
            # المرحلة 3: اختيار أفضل 30 للتحليل الذكي
            print("🎯 Phase 3: Selecting top 30 for AI analysis...")
            
            sorted_coins = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
            top_30 = sorted_coins[:30]
            
            print(f"   ✅ Top 30 selected for AI analysis")
            
            # المرحلة 4: تحليل ذكي للـ30 الأفضل
            if self.ai_brain or self.mtf_analyzer:
                print("🧠 Phase 4: AI deep analysis on top 30...")
                
                ai_scores = {}
                for idx, (symbol, base_score) in enumerate(top_30, 1):
                    try:
                        ai_score = self._analyze_coin_with_ai(symbol, base_score)
                        if ai_score > 0:
                            ai_scores[symbol] = ai_score
                        
                        # طباعة التقدم كل 20 عملة بدل 10
                        if idx % 20 == 0:
                            print(f"   Progress: {idx}/30 coins analyzed with AI...")
                    except Exception as e:
                        # إذا فشل AI، استخدم الـScore الأساسي
                        ai_scores[symbol] = base_score
                        print(f"   ⚠️ AI analysis failed for {symbol}: {e}")
                    
                    # تنظيف
                    gc.collect()
                
                # ترتيب حسب AI Score
                sorted_ai = sorted(ai_scores.items(), key=lambda x: x[1], reverse=True)
                top_20 = sorted_ai[:20]
                
                print(f"   ✅ AI analysis complete (30 coins analyzed)")
            else:
                # بدون AI، استخدم أفضل 20 من الـ30
                top_20 = top_30[:20]
                print(f"   ⚠️ AI not available, using top 20 from basic analysis")
            
            # المرحلة 5: تحديث القائمة
            print("🏆 Phase 5: Updating top 20 list...")
            with self.coins_lock:
                old_top = [coin for coin, score in self.top_coins]
                self.top_coins = top_20
                self.last_deep_scan = datetime.now()
                
                # طباعة التغييرات
                new_top = [coin for coin, score in top_20]
                
                added = [c for c in new_top if c not in old_top]
                removed = [c for c in old_top if c not in new_top]
                
                if added or removed:
                    # طباعة صامتة - بدون عرض تحديثات القائمة
                    pass
            
            elapsed = time.time() - start_time
            # طباعة صامتة - بدون عرض تفاصيل Deep Scan
            pass
        
        except Exception as e:
            print(f"❌ Deep scan error: {e}")
    
    def _calculate_hot_score(self, volume, price_change):
        """حساب score للفرص الساخنة"""
        score = 0
        
        # Volume score (0-50)
        if volume > 50_000_000:
            score += 50
        elif volume > 20_000_000:
            score += 40
        elif volume > 10_000_000:
            score += 30
        elif volume > 5_000_000:
            score += 20
        
        # Price change score (0-50)
        abs_change = abs(price_change)
        if abs_change > 5:
            score += 50
        elif abs_change > 4:
            score += 40
        elif abs_change > 3:
            score += 30
        elif abs_change > 2:
            score += 20
        
        return score
    
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
        with self.coins_lock:
            return self.top_coins.copy()
    
    def get_hot_opportunities(self):
        """الحصول على الفرص الساخنة"""
        with self.coins_lock:
            return self.hot_opportunities.copy()
    
    def get_scan_status(self):
        """حالة الفحص"""
        with self.coins_lock:
            return {
                'last_deep_scan': self.last_deep_scan,
                'last_quick_scan': self.last_quick_scan,
                'top_coins_count': len(self.top_coins),
                'hot_opportunities_count': len(self.hot_opportunities)
            }
