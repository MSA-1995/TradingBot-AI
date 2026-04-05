"""
🔴 Sell Handler
Processes SELL results and handles AI learning after a successful sell.
"""

import sys
import os

# إضافة مسار src للاستيراد
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from datetime import datetime
from colorama import Fore, Style
import json

from utils import execute_sell, calculate_sell_value
from notifications import send_sell_notification


def process_sell(result, exchange, ctx):
    """
    Process a SELL action result.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, storage,
              exit_strategy, pattern_recognizer, sell_cooldown,
              meta, advisor_manager
    Returns: True if sell executed successfully, False otherwise.
    """
    symbol          = result['symbol']
    SYMBOLS_DATA    = ctx['SYMBOLS_DATA']
    symbols_data_lock = ctx['symbols_data_lock']
    storage         = ctx['storage']
    advisor_manager = ctx.get('advisor_manager')
    meta            = ctx.get('meta')
    sell_cooldown   = ctx.get('sell_cooldown', {})
    dl_client       = ctx.get('dl_client')

    print(f"{Fore.RED}🔴 SELL {symbol} | {result['reason']} | Profit: {result['profit']:+.2f}%{Style.RESET_ALL}")

    sell_result = execute_sell(exchange, symbol, result['amount'], result['reason'])
    if not sell_result['success']:
        return False

    sell_cooldown[symbol] = datetime.now()

    sell_value = calculate_sell_value(result['amount'], result['price'])
    send_sell_notification(
        symbol, result['amount'], result['price'],
        sell_value, result['profit'], result['reason']
    )

    position = result['position']

    # AI Learning with instant evaluation
    try:
        hours_held = 24
        try:
            buy_time_str = position.get('buy_time')
            if buy_time_str:
                buy_time = datetime.fromisoformat(buy_time_str)
                hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        except:
            pass

        profit = result.get('profit', 0)
        
        # تقييم فوري للصفقة
        if profit >= 1.5:
            trade_quality = 'GREAT'
        elif profit >= 0.8:
            trade_quality = 'GOOD'
        elif profit >= 0.3:
            trade_quality = 'OK'
        elif profit >= -0.5:
            trade_quality = 'RISKY'
        else:
            trade_quality = 'TRAP'

        # جلب أصوات المستشارين للبيع (من result) والشراء (من position)
        sell_votes = result.get('sell_votes', {})
        buy_votes = position.get('advisor_votes', {})
        
        # جلب بيانات الأخبار والسيولة لحفظها في بيانات الصفقة
        news_data = {}
        sentiment_data = {}
        liquidity_data = {}
        try:
            news_analyzer = advisor_manager.get('NewsAnalyzer') if advisor_manager else None
            if news_analyzer:
                # محاولة بـ 24 ساعة أولاً، بعدين 48 ساعة، بعدين 72 ساعة
                news_sentiment = None
                for hours in [24, 48, 72]:
                    news_sentiment = news_analyzer.get_news_sentiment(symbol, hours=hours)
                    if news_sentiment:
                        break
                
                if news_sentiment:
                    news_data = {
                        'positive': news_sentiment.get('positive', 0),
                        'negative': news_sentiment.get('negative', 0),
                        'neutral': news_sentiment.get('neutral', 0),
                        'total': news_sentiment.get('total', 0),
                        'news_score': news_sentiment.get('news_score', 0)
                    }
                    sentiment_data = {
                        'news_sentiment': news_sentiment.get('news_score', 0)
                    }
        except:
            pass

        # جلب بيانات السيولة من الصفقة
        try:
            ai_data = position.get('ai_data', {})
            if ai_data:
                liquidity_data = {
                    'depth_ratio': ai_data.get('depth_ratio', 1.0),
                    'spread_percent': ai_data.get('spread_percent', 0.1),
                    'liquidity_score': ai_data.get('liquidity_score', 50),
                    'price_impact': ai_data.get('price_impact', 0.5),
                    'volume_consistency': ai_data.get('volume_consistency', 50)
                }
        except:
            pass

        # حفظ بيانات الصفقة
        trade_data = {
            'symbol': symbol,
            'action': 'sell',
            'profit_percent': profit,
            'trade_quality': trade_quality,
            'sell_reason': result.get('reason'),
            'hours_held': hours_held,
            'sell_votes': sell_votes,
            'buy_votes': buy_votes,
            'data': {
                'buy_price': position.get('buy_price'),
                'sell_price': result.get('price'),
                'ai_data': position.get('ai_data', {}),
                'news': news_data,
                'sentiment': sentiment_data,
                'liquidity': liquidity_data
            }
        }

        # حساب الميزات المتقدمة للتدريب
        analysis = result.get('analysis', {})
        price = analysis.get('close', 1)
        volume_ratio = analysis.get('volume_ratio', 1)

        # Liquidity Features
        order_book = analysis.get('order_book', {})
        bids_volume = sum(float(level[1]) for level in order_book.get('bids', [])[:10])
        asks_volume = sum(float(level[1]) for level in order_book.get('asks', [])[:10])
        total_volume = bids_volume + asks_volume
        order_book_imbalance = (bids_volume - asks_volume) / max(total_volume, 1) if total_volume > 0 else 0

        spread = analysis.get('bid_ask_spread', 0.001)
        avg_spread = analysis.get('average_spread', 0.001)
        spread_volatility = abs(spread - avg_spread) / max(avg_spread, 0.0001)

        depth_at_1pct = 0
        for level in order_book.get('bids', []):
            if abs(float(level[0]) - price) / price <= 0.01:
                depth_at_1pct += float(level[1])
        for level in order_book.get('asks', []):
            if abs(float(level[0]) - price) / price <= 0.01:
                depth_at_1pct += float(level[1])

        market_impact_score = min(volume_ratio / 10, 1.0)
        liquidity_trends = 0
        if volume_ratio > 1.5 and spread_volatility < 0.5:
            liquidity_trends = 1
        elif volume_ratio < 0.7 or spread_volatility > 1.0:
            liquidity_trends = -1

        # Risk Features
        volatility_risk_score = analysis.get('atr', 0) / price * 100
        correlation_risk = 0  # placeholder
        gap_risk_score = 0  # placeholder
        black_swan_probability = 0  # placeholder
        behavioral_risk = 0  # placeholder
        systemic_risk = 0  # placeholder

        # Exit Features
        profit_optimization_score = profit / 10
        time_decay_signals = min(hours_held / 24, 1)
        opportunity_cost_exits = 0  # placeholder
        market_condition_exits = 0  # placeholder

        # Pattern Features
        harmonic_patterns_score = 0  # placeholder
        elliott_wave_signals = 0  # placeholder
        fractal_patterns = 0  # placeholder
        cycle_patterns = 0  # placeholder
        momentum_patterns = 0  # placeholder

        # Smart Money Features
        whale_wallet_changes = 0  # placeholder
        institutional_accumulation = 0  # placeholder
        smart_money_ratio = 0  # placeholder
        exchange_whale_flows = 0  # placeholder

        # Anomaly Features
        statistical_outliers = 0  # placeholder
        pattern_anomalies = 0  # placeholder
        behavioral_anomalies = 0  # placeholder
        volume_anomalies = 0  # placeholder

        # Chart CNN Features
        attention_mechanism_score = 0  # placeholder
        multi_scale_features = 0  # placeholder
        temporal_features = 0  # placeholder

        # Volume Features
        volume_trend_strength = analysis.get('volume_trend', 0)
        volume_volatility = 0  # placeholder
        volume_momentum = 0  # placeholder
        volume_seasonality = 0  # placeholder
        volume_correlation = 0  # placeholder

        # Meta Features
        dynamic_consultant_weights = 0  # placeholder
        uncertainty_quantification = 0  # placeholder
        context_aware_score = 0  # placeholder

        # Add to trade_data
        trade_data.update({
            'order_book_imbalance': float(order_book_imbalance or 0),
            'spread_volatility': float(spread_volatility or 0),
            'depth_at_1pct': float(depth_at_1pct or 0),
            'market_impact_score': float(market_impact_score or 0),
            'liquidity_trends': float(liquidity_trends or 0),
            'volatility_risk_score': float(volatility_risk_score or 0),
            'correlation_risk': float(correlation_risk or 0),
            'gap_risk_score': float(gap_risk_score or 0),
            'black_swan_probability': float(black_swan_probability or 0),
            'behavioral_risk': float(behavioral_risk or 0),
            'systemic_risk': float(systemic_risk or 0),
            'profit_optimization_score': float(profit_optimization_score or 0),
            'time_decay_signals': float(time_decay_signals or 0),
            'opportunity_cost_exits': float(opportunity_cost_exits or 0),
            'market_condition_exits': float(market_condition_exits or 0),
            'harmonic_patterns_score': float(harmonic_patterns_score or 0),
            'elliott_wave_signals': float(elliott_wave_signals or 0),
            'fractal_patterns': float(fractal_patterns or 0),
            'cycle_patterns': float(cycle_patterns or 0),
            'momentum_patterns': float(momentum_patterns or 0),
            'whale_wallet_changes': float(whale_wallet_changes or 0),
            'institutional_accumulation': float(institutional_accumulation or 0),
            'smart_money_ratio': float(smart_money_ratio or 0),
            'exchange_whale_flows': float(exchange_whale_flows or 0),
            'statistical_outliers': float(statistical_outliers or 0),
            'pattern_anomalies': float(pattern_anomalies or 0),
            'behavioral_anomalies': float(behavioral_anomalies or 0),
            'volume_anomalies': float(volume_anomalies or 0),
            'attention_mechanism_score': float(attention_mechanism_score or 0),
            'multi_scale_features': float(multi_scale_features or 0),
            'temporal_features': float(temporal_features or 0),
            'volume_trend_strength': float(volume_trend_strength or 0),
            'volume_volatility': float(volume_volatility or 0),
            'volume_momentum': float(volume_momentum or 0),
            'volume_seasonality': float(volume_seasonality or 0),
            'volume_correlation': float(volume_correlation or 0),
            'dynamic_consultant_weights': float(dynamic_consultant_weights or 0),
            'uncertainty_quantification': float(uncertainty_quantification or 0),
            'context_aware_score': float(context_aware_score or 0),
            'rsi': float(analysis.get('rsi', 50) or 0),
            'volume_ratio': float(volume_ratio or 1),
            'sentiment_score': float(analysis.get('sentiment_score', 0) or 0),
            'panic_score': float(analysis.get('panic_score', 0) or 0)
        })
        # تحديث ذاكرة العملة
        try:
            if hasattr(storage.storage, 'update_symbol_memory'):
                storage.storage.update_symbol_memory(
                    symbol=symbol,
                    profit=float(profit),
                    trade_quality=str(trade_quality),
                    hours_held=float(hours_held),
                    rsi=float(position.get('ai_data', {}).get('rsi', 50)),
                    volume_ratio=float(position.get('ai_data', {}).get('volume_ratio', 1))
                )
        except Exception as e:
            print(f"⚠️ Symbol memory update error: {e}")

        storage.save_trade(trade_data)
        
        # =========================================================
        # 🎓 التعلم المباشر للملك والمستشارين - حفظ في الداتابيز
        # =========================================================
        
        # حفظ بيانات التعلم
        try:
            # تعلم المستشارين (dl_client)
            if dl_client:
                dl_client.learn_from_trade(profit, trade_quality, buy_votes, sell_votes, signal_type='sell')

            # تعلم الملك (مع symbol للقائمة السوداء)
            if meta:
                meta.learn_from_trade(profit, trade_quality, buy_votes, sell_votes, symbol=symbol)
            
            king_learning_data = {
                'king': {
                    'buy_success': 1 if profit > 0.5 else 0,
                    'buy_fail': 1 if profit < -0.5 else 0,
                    'sell_success': 1 if trade_quality in ['GREAT', 'GOOD', 'OK'] else 0,
                    'sell_fail': 1 if trade_quality in ['RISKY', 'TRAP'] else 0,
                    'peak_correct': 1 if trade_quality in ['GREAT', 'GOOD', 'OK'] else 0,
                    'peak_wrong': 1 if trade_quality in ['RISKY', 'TRAP'] else 0,
                    'bottom_correct': 1 if profit > 0.5 else 0,
                    'bottom_wrong': 1 if profit < -0.5 else 0
                }
            }
            storage.save_learning_data('king', king_learning_data)
            
            # تعلم المستشارين (من أصوات البيع)
            advisor_learning_data = {}
            for advisor, voted in sell_votes.items():
                if trade_quality in ['GREAT', 'GOOD', 'OK']:
                    advisor_learning_data[advisor] = {
                        'sell_success': 1 if voted == 1 else 0,
                        'sell_fail': 0 if voted == 1 else 1
                    }
                elif trade_quality in ['RISKY', 'TRAP']:
                    advisor_learning_data[advisor] = {
                        'sell_success': 0 if voted == 1 else 1,
                        'sell_fail': 1 if voted == 1 else 0
                    }
            if advisor_learning_data:
                storage.save_learning_data('advisors', advisor_learning_data)
            
            print(f"🎓 Learning saved to database")
            
        except Exception as e:
            print(f"⚠️ Learning save error: {e}")
        
        quality_emoji = '🟢' if trade_quality in ['GREAT', 'GOOD'] else ('🟡' if trade_quality == 'OK' else '🔴')
        print(f"{quality_emoji} Trade Quality: {trade_quality} | Profit: {profit:+.2f}% | Held: {hours_held:.1f}h")
        
    except Exception as e:
        print(f"⚠️ Error saving trade for {symbol}: {e}")

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = None

    try:
        storage.delete_position(symbol)
        print(f"✅ {symbol} position deleted from database.")
    except Exception as e:
        print(f"⚠️ Error deleting {symbol} from database: {e}")

    return True
