"""
🔴 Sell Handler
Processes SELL results and handles AI learning after a successful sell.
"""

import sys
import os
import logging
logger = logging.getLogger(__name__)

# Add src path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir     = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from datetime import datetime, timezone
from colorama import Fore, Style
import json

from utils import execute_sell, calculate_sell_value
from notifications import send_sell_notification, send_advisor_report


def process_sell(result, exchange, ctx):
    """
    Process a SELL action result.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, storage,
              exit_strategy, pattern_recognizer, sell_cooldown,
              meta, advisor_manager
    Returns: True if sell executed successfully, False otherwise.
    """
    symbol            = result['symbol']
    SYMBOLS_DATA      = ctx['SYMBOLS_DATA']
    symbols_data_lock = ctx['symbols_data_lock']
    storage           = ctx['storage']
    advisor_manager   = ctx.get('advisor_manager')
    meta              = ctx.get('meta')
    sell_cooldown     = ctx.get('sell_cooldown', {})
    dl_client         = ctx.get('dl_client')

    voting_display = ""
    if 'sell_vote_percentage' in result:
        sell_vote_percentage = result.get('sell_vote_percentage', 0)
        sell_vote_count      = result.get('sell_vote_count', 0)
        total_advisors       = result.get('total_advisors', 0)
        voting_display       = f" | 🗳️ Sell:{sell_vote_percentage:.0f}% ({sell_vote_count}/{total_advisors})"

    print(f"{Fore.RED}🔴 SELL {symbol} | Price:${result['price']:.4f} | Amount:${result['amount']:.2f} | Profit: {result['profit']:+.2f}%{voting_display} | {result['reason']}{Style.RESET_ALL}")

    sell_result = execute_sell(exchange, symbol, result['amount'], result['reason'])
    if not sell_result['success']:
        return False

    sell_cooldown[symbol] = datetime.now(timezone.utc)

    sell_value = calculate_sell_value(result['amount'], result['price'])

    send_sell_notification(
        symbol         = symbol,
        amount         = result['amount'],
        price          = result['price'],
        value          = sell_value,
        profit_percent = result['profit'],
        reason         = result['reason']
    )

    # 📊 Send Advisor Report (only Peak Points)
    try:
        _reason = result.get('reason', '')
        if 'Peak Points' in _reason:
            _sell_votes = result.get('sell_votes', {})
            send_advisor_report(
            signal_type='SELL',
            symbol=symbol,
            core_votes=_sell_votes,
            meta_confidence=result.get('confidence', 0),
            total_points=result.get('confidence', 0),
            profit_percent=result.get('profit', 0),
            reason=result.get('reason', ''),
        )
    except Exception as e:
        print(f"⚠️ [{symbol}] Advisor report error: {e}")

    position = result['position']

    try:
        hours_held = 24
        try:
            buy_time_str = position.get('buy_time')
            if buy_time_str:
                buy_time   = datetime.fromisoformat(buy_time_str)
                hours_held = (datetime.now() - buy_time).total_seconds() / 3600
        except Exception:
            pass

        profit = result.get('profit', 0)

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

        sell_votes = result.get('sell_votes', {})
        buy_votes  = position.get('advisor_votes', {})

        analysis = result.get('analysis', {}) or {}

        news_data            = {}
        sentiment_data       = {}
        liquidity_data       = {}
        real_sentiment_score = 0.0
        real_panic_score     = 0.0

        try:
            news_analyzer = advisor_manager.get('NewsAnalyzer') if advisor_manager else None
            if news_analyzer:
                news_sentiment = None
                for hours in [24, 48, 72]:
                    news_sentiment = news_analyzer.get_news_sentiment(symbol, hours=hours)
                    if news_sentiment:
                        break

                if news_sentiment:
                    news_data = {
                        'positive':   news_sentiment.get('positive', 0),
                        'negative':   news_sentiment.get('negative', 0),
                        'neutral':    news_sentiment.get('neutral', 0),
                        'total':      news_sentiment.get('total', 0),
                        'news_score': news_sentiment.get('news_score', 0)
                    }
                    sentiment_data = {
                        'news_sentiment': news_sentiment.get('news_score', 0)
                    }

            try:
                from news_analyzer import get_sentiment_data
                market_sentiment     = get_sentiment_data(symbol, analysis)
                real_sentiment_score = market_sentiment.get('sentiment_score', 0.0)
                real_panic_score     = market_sentiment.get('panic_score', 0.0)
            except Exception as e:
                logger.warning(f"get_sentiment_data error: {e}")
                real_panic_score = float(analysis.get('panic_greed', {}).get('panic_score', 0) or 0)

        except Exception:
            pass

        try:
            ai_data = position.get('ai_data', {})
            if ai_data:
                liquidity_data = {
                    'depth_ratio':        ai_data.get('depth_ratio', 1.0),
                    'spread_percent':     ai_data.get('spread_percent', 0.1),
                    'liquidity_score':    ai_data.get('liquidity_score', 50),
                    'price_impact':       ai_data.get('price_impact', 0.5),
                    'volume_consistency': ai_data.get('volume_consistency', 50)
                }
        except Exception:
            pass

        candles_data = []
        try:
            raw_candles = analysis.get('candles', [])
            if raw_candles and isinstance(raw_candles, list) and len(raw_candles) > 0:
                for candle in raw_candles[-7:]:
                    if isinstance(candle, dict):
                        candle_open   = float(candle.get('open', 0))
                        candle_high   = float(candle.get('high', 0))
                        candle_low    = float(candle.get('low', 0))
                        candle_close  = float(candle.get('close', 0))
                        candle_volume = float(candle.get('volume', 0))

                        if candle_open > 0 and candle_high > 0 and candle_low > 0 and candle_close > 0:
                            candles_data.append({
                                'open':   candle_open,
                                'high':   candle_high,
                                'low':    candle_low,
                                'close':  candle_close,
                                'volume': candle_volume
                            })

                if len(candles_data) > 0:
                    print(f"✅ Saved {len(candles_data)} candles for {symbol}")
        except Exception as e:
            print(f"⚠️ Candles extraction error: {e}")
            candles_data = []

        trade_data = {
            'symbol':        symbol,
            'action':        'sell',
            'profit_percent': profit,
            'trade_quality': trade_quality,
            'sell_reason':   result.get('reason'),
            'hours_held':    hours_held,
            'sell_votes':    sell_votes,
            'buy_votes':     buy_votes,
            'data': {
                'buy_price':  position.get('buy_price', 0),
                'sell_price': result.get('price'),
                'candles':    candles_data,
                'ai_data':    position.get('ai_data', {}),
                'news':       news_data,
                'sentiment':  sentiment_data,
                'liquidity':  liquidity_data
            }
        }

        volume_ratio = result.get('volume_ratio', 1.0)
        rsi          = result.get('rsi', 50)

        def safe_float(value, default=0.0):
            try:
                return float(value) if value is not None else default
            except Exception:
                return default

        trade_data.update({
            'order_book_imbalance':       safe_float(result.get('order_book_imbalance')),
            'spread_volatility':          safe_float(result.get('spread_volatility')),
            'depth_at_1pct':              safe_float(result.get('depth_at_1pct')),
            'market_impact_score':        safe_float(result.get('market_impact_score')),
            'liquidity_trends':           safe_float(result.get('liquidity_trends')),
            'volatility_risk_score':      safe_float(result.get('volatility_risk_score')),
            'correlation_risk':           safe_float(result.get('correlation_risk')),
            'gap_risk_score':             safe_float(result.get('gap_risk_score')),
            'black_swan_probability':     safe_float(result.get('black_swan_probability')),
            'behavioral_risk':            safe_float(result.get('behavioral_risk')),
            'systemic_risk':              safe_float(result.get('systemic_risk')),
            'profit_optimization_score':  safe_float(result.get('profit_optimization_score')),
            'time_decay_signals':         safe_float(result.get('time_decay_signals')),
            'opportunity_cost_exits':     safe_float(result.get('opportunity_cost_exits')),
            'market_condition_exits':     safe_float(result.get('market_condition_exits')),
            'harmonic_patterns_score':    safe_float(result.get('harmonic_patterns_score')),
            'elliott_wave_signals':       safe_float(result.get('elliott_wave_signals')),
            'fractal_patterns':           safe_float(result.get('fractal_patterns')),
            'cycle_patterns':             safe_float(result.get('cycle_patterns')),
            'momentum_patterns':          safe_float(result.get('momentum_patterns')),
            'whale_wallet_changes':       safe_float(result.get('whale_wallet_changes')),
            'institutional_accumulation': safe_float(result.get('institutional_accumulation')),
            'smart_money_ratio':          safe_float(result.get('smart_money_ratio')),
            'exchange_whale_flows':       safe_float(result.get('exchange_whale_flows')),
            'statistical_outliers':       safe_float(result.get('statistical_outliers')),
            'pattern_anomalies':          safe_float(result.get('pattern_anomalies')),
            'behavioral_anomalies':       safe_float(result.get('behavioral_anomalies')),
            'volume_anomalies':           safe_float(result.get('volume_anomalies')),
            'attention_mechanism_score':  safe_float(result.get('attention_mechanism_score')),
            'multi_scale_features':       safe_float(result.get('multi_scale_features')),
            'temporal_features':          safe_float(result.get('temporal_features')),
            'volume_trend_strength':      safe_float(result.get('volume_trend_strength')),
            'volume_volatility':          safe_float(result.get('volume_volatility')),
            'volume_momentum':            safe_float(result.get('volume_momentum')),
            'volume_seasonality':         safe_float(result.get('volume_seasonality')),
            'volume_correlation':         safe_float(result.get('volume_correlation')),
            'dynamic_consultant_weights': safe_float(result.get('dynamic_consultant_weights')),
            'uncertainty_quantification': safe_float(result.get('uncertainty_quantification')),
            'context_aware_score':        safe_float(result.get('context_aware_score')),
            'rsi':                        safe_float(rsi, 50),
            'volume_ratio':               safe_float(volume_ratio, 1.0),
            'whale_confidence':           safe_float(result.get('whale_confidence'), 0),
            'atr_value':                  safe_float(result.get('atr_value'), 0),
            'sentiment_score':            safe_float(real_sentiment_score),
            'panic_score':                safe_float(real_panic_score),
            'optimism_penalty':           safe_float(result.get('optimism_penalty', 0)),
            'psychological_analysis':     result.get('psychological_analysis', ''),
            'profit':                     safe_float(trade_data.get('profit_percent', 0))
        })

        try:
            if meta and hasattr(meta, 'db_manager'):
                symbol_memory_data          = meta.db_manager.load_symbol_memory()
                trade_data['symbol_memory'] = symbol_memory_data.get(symbol, {})
                trade_data['trades_history'] = trade_data['symbol_memory'].get('total_trades', 0)
        except Exception as e:
            trade_data['symbol_memory']  = {}
            trade_data['trades_history'] = 0

        storage.save_trade(trade_data)

        try:
            extra_data = {
                'sentiment':        real_sentiment_score,
                'panic':            real_panic_score,
                'whale_confidence': result.get('whale_confidence', 0),
                'volume_trend':     analysis.get('volume_trend_strength', 0),
                'optimism':         result.get('optimism_penalty', 0)
            }

            if dl_client:
                dl_client.learn_from_trade(profit, trade_quality, buy_votes, sell_votes, signal_type='sell')

            if meta:
                meta.learn_from_trade(profit, trade_quality, buy_votes, sell_votes, symbol=symbol, position=position, extra_data=extra_data)

            print(f"🎓 Learning saved to database")

        except Exception as e:
            print(f"⚠️ Learning save error: {e}")

        quality_emoji = '🟢' if trade_quality in ['GREAT', 'GOOD'] else ('🟡' if trade_quality == 'OK' else '🔴')
        print(f"{quality_emoji} Trade Quality: {trade_quality} | Profit: {profit:+.2f}% | Held: {hours_held:.1f}h")

    except Exception as e:
        logging.error(f"Error saving trade for {symbol}: {e}", exc_info=True)
        print(f"⚠️ Error saving trade for {symbol}: {e}")

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = None

    try:
        storage.delete_position(symbol)
        print(f"✅ {symbol} position deleted from database.")
    except Exception as e:
        logging.error(f"Error deleting position {symbol}: {e}", exc_info=True)
        print(f"⚠️ Error deleting {symbol} from database: {e}")

    return True
