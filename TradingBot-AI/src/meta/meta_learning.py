"""
🧠 Meta Learning
التعلم من الصفقات + الذاكرة الذكية
"""

import gc
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_LEARNING_KEY = 'king_learning_data'


class LearningMixin:
    """Mixin يحتوي على كل منطق التعلم"""

    def learn_from_trade(self, profit: float, trade_quality: str,
                          buy_votes: dict, sell_votes: dict,
                          symbol: str = None, position: dict = None,
                          extra_data: dict = None) -> None:
        """التعلم المباشر من كل صفقة"""
        try:
            data      = self._load_learning_data()
            ai_data   = position.get('ai_data', {}) if position else {}
            rsi       = ai_data.get('rsi', 50)
            vol_ratio = ai_data.get('volume_ratio', ai_data.get('volume', 1.0))
            macd_diff = ai_data.get('macd_diff', 0)
            buy_conf  = position.get('buy_confidence', 50) if position else 50
            hour      = datetime.now().hour
            hour_key  = str(hour)

            cur_rsi  = extra_data.get('rsi', 50) if extra_data else rsi
            optimism = extra_data.get('optimism', 0) if extra_data else 0
            if optimism == 0 and cur_rsi > 75:
                optimism = (cur_rsi - 75) * 0.8

            success_qualities = {'GREAT', 'GOOD', 'OK'}
            fail_qualities    = {'RISKY', 'TRAP'}

            # ── تعلم من البيع ──
            sv_count = (len([v for v in sell_votes.values() if v == 1])
                        if sell_votes else 0)
            if trade_quality in success_qualities:
                data['sell_success'] += 1
                if sv_count >= 4:
                    data['peak_correct'] += 1
            elif trade_quality in fail_qualities:
                data['sell_fail'] += 1
                if sv_count >= 4:
                    data['peak_wrong'] += 1

            # ── تعلم من الشراء ──
            if profit > 5.0:
                data['buy_success'] += 1
                pos_votes = sum(
                    1 for v in buy_votes.values()
                    if 'Bullish' in str(v)
                ) if buy_votes else 0
                if pos_votes >= 3:
                    data['bottom_correct'] += 1
            elif profit < -0.5:
                data['buy_fail'] += 1
                bv_count = (len([v for v in buy_votes.values() if v == 1])
                            if buy_votes else 0)
                if bv_count >= 3:
                    data['bottom_wrong'] += 1

            # ── ذاكرة ذكية عند النجاح ──
            if trade_quality in success_qualities:
                self._record_success(
                    data, symbol, hour, hour_key,
                    rsi, vol_ratio, macd_diff, buy_conf, profit)

            # ── ذاكرة ذكية عند الفشل ──
            if profit < -0.5 or trade_quality in fail_qualities:
                self._record_failure(
                    data, symbol, hour_key,
                    rsi, vol_ratio, buy_conf, trade_quality, profit)

            self._save_learning_data(data)
            self._update_memory_columns(
                symbol, position, data, rsi, vol_ratio,
                macd_diff, buy_conf, profit, trade_quality,
                sell_votes, buy_votes, extra_data, ai_data, optimism)

            total = (data['buy_success'] + data['buy_fail']
                     + data['sell_success'] + data['sell_fail'])
            if total > 0:
                success  = data['buy_success'] + data['sell_success']
                accuracy = success / total * 100
                print(f"👑 King learned: {trade_quality} | "
                      f"Accuracy: {accuracy:.0f}% ({success}/{total})")

        except Exception as e:
            print(f"⚠️ King learning error: {e}")

    def _record_success(self, data: dict, symbol: str, hour: int,
                         hour_key: str, rsi: float, vol_ratio: float,
                         macd_diff: float, buy_conf: float,
                         profit: float) -> None:
        """تسجيل بيانات الصفقة الناجحة"""
        data['best_buy_times'].setdefault(symbol, {})
        data['best_buy_times'][symbol][hour_key] = (
            data['best_buy_times'][symbol].get(hour_key, 0) + 1)

        data['successful_patterns'].append({
            'symbol':       symbol,
            'rsi':          rsi,
            'volume_ratio': vol_ratio,
            'macd_diff':    macd_diff,
            'confidence':   buy_conf,
            'profit':       profit,
            'hour':         hour,
            'date':         datetime.now(timezone.utc).isoformat()
        })
        if len(data['successful_patterns']) > self.MAX_PATTERNS:
            data['successful_patterns'] = \
                data['successful_patterns'][-self.MAX_PATTERNS:]

        if rsi < 40 or vol_ratio > 2.0:
            data['courage_record'].append({
                'symbol':       symbol,
                'rsi':          rsi,
                'volume_ratio': vol_ratio,
                'confidence':   buy_conf,
                'profit':       profit,
                'hour':         hour,
                'date':         datetime.now().isoformat()
            })
            if len(data['courage_record']) > self.MAX_COURAGE_RECORDS:
                data['courage_record'] = \
                    data['courage_record'][-self.MAX_COURAGE_RECORDS:]

        data['symbol_win_rate'].setdefault(symbol, {'wins': 0, 'total': 0})
        data['symbol_win_rate'][symbol]['wins']  += 1
        data['symbol_win_rate'][symbol]['total'] += 1

        bucket = str(int(buy_conf // 10) * 10)
        data['confidence_calibration'].setdefault(
            bucket, {'wins': 0, 'total': 0})
        data['confidence_calibration'][bucket]['wins']  += 1
        data['confidence_calibration'][bucket]['total'] += 1

    def _record_failure(self, data: dict, symbol: str, hour_key: str,
                         rsi: float, vol_ratio: float, buy_conf: float,
                         trade_quality: str, profit: float) -> None:
        """تسجيل بيانات الصفقة الفاشلة"""
        data['worst_buy_times'].setdefault(symbol, {})
        data['worst_buy_times'][symbol][hour_key] = (
            data['worst_buy_times'][symbol].get(hour_key, 0) + 1)

        data['symbol_win_rate'].setdefault(symbol, {'wins': 0, 'total': 0})
        data['symbol_win_rate'][symbol]['total'] += 1

        bucket = str(int(buy_conf // 10) * 10)
        data['confidence_calibration'].setdefault(
            bucket, {'wins': 0, 'total': 0})
        data['confidence_calibration'][bucket]['total'] += 1

        reason = ('trap'        if trade_quality == 'TRAP'
                  else 'low_profit' if profit < -0.5
                  else 'other')
        data['error_history'].append({
            'symbol':       symbol,
            'rsi':          rsi,
            'volume_ratio': vol_ratio,
            'reason':       reason,
            'date':         datetime.now().isoformat()
        })
        if len(data['error_history']) > self.MAX_ERROR_HISTORY:
            data['error_history'] = \
                data['error_history'][-self.MAX_ERROR_HISTORY:]

    def _update_memory_columns(self, symbol: str, position,
                                data: dict, rsi: float,
                                vol_ratio: float, macd_diff: float,
                                buy_conf: float, profit: float,
                                trade_quality: str, sell_votes: dict,
                                buy_votes: dict, extra_data,
                                ai_data: dict, optimism: float) -> None:
        """تحديث أعمدة الذاكرة في الداتابيز"""
        try:
            c_boost    = self._get_courage_boost(symbol, rsi, vol_ratio)
            t_mod, _   = self._get_time_memory_modifier(symbol)
            p_score, _ = self._get_symbol_pattern_score(
                symbol, rsi, macd_diff, vol_ratio)
            w_boost, _ = self._get_symbol_win_rate_boost(symbol)

            swr = data.get('symbol_win_rate', {}).get(
                symbol, {'wins': 0, 'total': 1})
            plr = (swr['wins'] / max(swr['total'] - swr['wins'], 1)
                   if swr.get('total', 1) > 1 else 1.0)

            sent = extra_data.get('sentiment', 0) if extra_data else 0
            panc = extra_data.get('panic',     0) if extra_data else 0
            psy  = ("Greed"   if sent > 2
                    else "Panic" if panc > 5
                    else "Neutral")

            if hasattr(self.storage, 'update_symbol_memory'):
                hours_held = 24.0
                if position:
                    try:
                        hours_held = float(
                            (datetime.now()
                             - datetime.fromisoformat(position['buy_time'])
                             ).total_seconds() / 3600)
                    except Exception:
                        hours_held = 24.0

                self.storage.update_symbol_memory(
                    symbol=symbol,
                    profit=profit,
                    trade_quality=trade_quality,
                    hours_held=hours_held,
                    rsi=rsi,
                    volume_ratio=vol_ratio,
                    sentiment=sent,
                    whale_conf=(extra_data.get('whale_confidence', 0)
                                if extra_data
                                else ai_data.get('whale_confidence', 0)),
                    panic=panc,
                    optimism=float(optimism),
                    profit_loss_ratio=plr,
                    volume_trend=(extra_data.get('volume_trend', 0)
                                  if extra_data else 0),
                    psychological_summary=psy,
                    courage_boost=c_boost,
                    time_memory_modifier=t_mod,
                    pattern_score=p_score,
                    win_rate_boost=w_boost
                )

            pattern_type = ('SUCCESS'
                            if trade_quality in {'GREAT', 'GOOD', 'OK'}
                            else 'TRAP')
            pattern_data = {
                'type':         pattern_type,
                'success_rate': (1.0 if trade_quality in {'GREAT', 'GOOD'}
                                 else 0.0),
                'features': {
                    'profit':        profit,
                    'trade_quality': trade_quality,
                    'sell_votes':    sell_votes,
                    'buy_votes':     buy_votes or {},
                    'symbol':        symbol
                }
            }
            self.storage.save_pattern(pattern_data)
            self._patterns_cache.append({
                'id':           None,
                'pattern_type': pattern_type,
                'data':         {'features': pattern_data['features']},
                'success_rate': pattern_data['success_rate']
            })
            if len(self._patterns_cache) > self.MAX_CACHE_PATTERNS:
                self._patterns_cache = \
                    self._patterns_cache[-self.MAX_CACHE_PATTERNS:]
            print(f"✅ Saved {pattern_type} pattern for {symbol}")

        except Exception as e:
            print(f"⚠️ Memory update error: {e}")

    def _load_learning_data(self) -> dict:
        """تحميل بيانات التعلم من الداتابيز"""
        default = {
            'buy_success':            0,
            'buy_fail':               0,
            'sell_success':           0,
            'sell_fail':              0,
            'peak_correct':           0,
            'peak_wrong':             0,
            'bottom_correct':         0,
            'bottom_wrong':           0,
            'best_buy_times':         {},
            'worst_buy_times':        {},
            'best_trade_sizes':       {},
            'successful_patterns':    [],
            'error_history':          [],
            'courage_record':         [],
            'symbol_win_rate':        {},
            'confidence_calibration': {}
        }

        try:
            if self.storage:
                raw = self.storage.load_setting(DB_LEARNING_KEY)
                if raw:
                    loaded = json.loads(raw) if isinstance(raw, str) else raw
                    for key, val in default.items():
                        loaded.setdefault(key, val)
                    gc.collect()
                    return loaded
        except Exception:
            pass

        try:
            local_file = 'data/king_learning.json'
            if os.path.exists(local_file):
                with open(local_file, 'r') as f:
                    file_data = json.load(f)
                self._save_learning_data(file_data)
                print("✅ Migrated king_learning.json to database")
                return file_data
        except Exception:
            pass

        return default

    def _save_learning_data(self, data: dict) -> None:
        """حفظ بيانات التعلم في الداتابيز"""
        try:
            if self.storage:
                self.storage.save_setting(
                    DB_LEARNING_KEY, json.dumps(data))
        except Exception as e:
            print(f"⚠️ Error saving learning data: {e}")

    def get_patterns_from_cache(self) -> list:
        """قراءة الأنماط من الرام"""
        return self._patterns_cache or []

    def get_learning_stats(self) -> dict:
        """إحصائيات تعلم الملك"""
        try:
            data    = self._load_learning_data()
            total   = (data['buy_success'] + data['buy_fail']
                       + data['sell_success'] + data['sell_fail'])
            success = data['buy_success'] + data['sell_success']

            symbol_stats = {
                sym: {'win_rate': round(w['wins'] / w['total'] * 100, 1),
                      'total':    w['total']}
                for sym, w in data.get('symbol_win_rate', {}).items()
                if w.get('total', 0) > 0
            }

            calib = {
                f"conf_{b}": {
                    'win_rate': round(cc['wins'] / cc['total'] * 100, 1),
                    'total':    cc['total']}
                for b, cc in data.get('confidence_calibration', {}).items()
                if cc.get('total', 0) >= 3
            }

            pk  = data['peak_correct']   + data['peak_wrong']
            btm = data['bottom_correct'] + data['bottom_wrong']

            return {
                'total':                  total,
                'success':                success,
                'accuracy':               (success / total * 100
                                           if total > 0 else 0),
                'peak_accuracy':          (data['peak_correct'] / pk * 100
                                           if pk > 0 else 0),
                'bottom_accuracy':        (data['bottom_correct'] / btm * 100
                                           if btm > 0 else 0),
                'patterns_stored':        len(data.get('successful_patterns', [])),
                'courage_records':        len(data.get('courage_record', [])),
                'symbol_win_rates':       symbol_stats,
                'confidence_calibration': calib
            }
        except Exception:
            return {
                'total': 0, 'success': 0, 'accuracy': 0,
                'peak_accuracy': 0, 'bottom_accuracy': 0
            }