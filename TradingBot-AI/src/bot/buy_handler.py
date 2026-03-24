"""
🟢 Buy Handler
Processes BUY results, sends notifications, and saves position data.
"""

from datetime import datetime
from colorama import Fore, Style

from trading import execute_buy
from notifications import send_buy_notification


def process_buy(result, exchange, ctx):
    """
    Process a BUY action result.
    ctx keys: SYMBOLS_DATA, symbols_data_lock, storage,
              smart_money_tracker, risk_manager, anomaly_detector,
              exit_strategy, pattern_recognizer, liquidity_analyzer
    Returns: True if buy executed successfully, False otherwise.
    Note: caller is responsible for updating active_count and available.
    """
    symbol             = result['symbol']
    SYMBOLS_DATA       = ctx['SYMBOLS_DATA']
    symbols_data_lock  = ctx['symbols_data_lock']
    storage            = ctx['storage']
    smart_money_tracker = ctx['smart_money_tracker']
    risk_manager       = ctx['risk_manager']
    anomaly_detector   = ctx['anomaly_detector']
    exit_strategy      = ctx['exit_strategy']
    pattern_recognizer = ctx['pattern_recognizer']
    liquidity_analyzer = ctx['liquidity_analyzer']

    news_display = f" | {result['news_summary']}" if result.get('news_summary') else ""

    voting_display = ""
    if 'decision' in result:
        decision = result['decision']
        buy_vote_percentage = decision.get('buy_vote_percentage')
        if buy_vote_percentage is not None:
            voting_display = f" | 🗳️ Buy:{buy_vote_percentage:.0f}% Amount:${result['amount']:.0f}"

    print(f"{Fore.GREEN}🟢 BUY {symbol} | Meta Confidence:{result['confidence']}{voting_display}{news_display}{Style.RESET_ALL}")

    buy_result = execute_buy(exchange, symbol, result['amount'], result['price'], result['confidence'])
    if not buy_result['success']:
        return False

    # Extract voting results if available
    tp_target = None
    sl_target = None
    buy_vote_percentage = None
    buy_vote_count = None
    total_consultants = None
    
    if 'decision' in result:
        decision = result['decision']
        buy_vote_percentage = decision.get('buy_vote_percentage')
        buy_vote_count = decision.get('buy_vote_count')
        total_consultants = decision.get('total_consultants')

    send_buy_notification(
        symbol, buy_result['amount'], result['price'], result['amount'],
        result['confidence'], tp_target, sl_target,
        buy_vote_percentage, buy_vote_count, total_consultants
    )

    # The learning process is now handled by the trainer, not the bot.
    # The old ai_brain.save_buy_voting_results call is removed.

    position_data = {
        'buy_price':    buy_result['price'],
        'amount':       buy_result['amount'],
        'highest_price': buy_result['price'],
        'buy_time':     datetime.now().isoformat()
    }

    if 'decision' in result:
        decision = result['decision']

        # Collect all advisor scores
        advisor_scores = {
            'confidence':   result['confidence'],
            'rsi':          result['analysis']['rsi'],
            'volume':       result['analysis']['volume'],
            'macd_diff':    result['analysis']['macd_diff'],
            'mtf_score':    0,
            'risk_score':   0,
            'anomaly_score': 0,
            'exit_score':   0,
            'pattern_score': 0,
            'ranking_score': 0
        }

        # Get Smart Money score
        if smart_money_tracker:
            try:
                sm_boost = smart_money_tracker.get_confidence_adjustment(symbol, result['analysis'])
                advisor_scores['smart_money_score'] = sm_boost
            except:
                pass

        # Get Risk score
        if risk_manager and isinstance(result.get('analysis'), dict):
            try:
                risk_score = risk_manager.get_risk_score(result['analysis'], result.get('confidence', 50))
                if risk_score is not None:
                    advisor_scores['risk_score'] = risk_score
            except Exception as e:
                print(f"Error getting risk score for {symbol}: {e}")

        # Get Anomaly score
        if anomaly_detector:
            try:
                anomaly_result = anomaly_detector.detect_anomalies(symbol, result['analysis'])
                if anomaly_result:
                    advisor_scores['anomaly_score'] = anomaly_result.get('anomaly_score', 0) or 0
            except:
                pass

        # Get Exit score
        if exit_strategy:
            try:
                exit_score = exit_strategy.get_entry_score(symbol, result['analysis'])
                if exit_score:
                    advisor_scores['exit_score'] = exit_score or 0
            except:
                pass

        # Get Pattern score
        if pattern_recognizer:
            try:
                safe_mtf        = {'trend': 'neutral', 'total': 0}
                safe_price_drop = {'drop_percent': 0, 'confirmed': False}
                pattern_analysis = pattern_recognizer.analyze_entry_pattern(
                    symbol, result['analysis'], safe_mtf, safe_price_drop
                )
                if pattern_analysis:
                    advisor_scores['pattern_score'] = pattern_analysis.get('confidence_adjustment', 0) or 0
            except:
                pass

        # Get Liquidity score
        if liquidity_analyzer:
            try:
                liquidity_check = liquidity_analyzer.should_trade_coin(symbol, result['analysis'])
                if liquidity_check:
                    advisor_scores['liquidity_score'] = liquidity_check.get('confidence_adjustment', 0) or 0
            except:
                pass

        position_data.update({
            'tp_target':      0,
            'sl_target':      0,
            'max_wait_hours': decision.get('max_wait_hours', 48),
            'ai_data':        advisor_scores
        })

    with symbols_data_lock:
        SYMBOLS_DATA[symbol]['position'] = position_data
    storage.save_positions(SYMBOLS_DATA)

    return True
