"""
التخزين المحلي - ملفات JSON
"""
import os
import json
from datetime import datetime

class LocalStorage:
    def __init__(self, base_path='data/'):
        self.base_path = base_path
        self.ensure_directories()
    
    def ensure_directories(self):
        """إنشاء المجلدات إذا لم تكن موجودة"""
        dirs = [
            'trades', 'learning', 'performance', 
            'config', 'cache'
        ]
        for d in dirs:
            os.makedirs(os.path.join(self.base_path, d), exist_ok=True)
    
    def _load_json(self, filepath, default=None):
        """تحميل ملف JSON"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f'⚠️ Load JSON error: {e}')
        return default if default is not None else []
    
    def _save_json(self, filepath, data):
        """حفظ ملف JSON"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error saving {filepath}: {e}")
            return False
    
    # ========== Trades ==========
    def save_trade(self, trade_data):
        filepath = os.path.join(self.base_path, 'trades', 'trades_history.json')
        trades = self._load_json(filepath, [])
        trade_data['timestamp'] = datetime.now().isoformat()
        trades.append(trade_data)
        return self._save_json(filepath, trades)
    
    def load_trades(self, limit=None):
        filepath = os.path.join(self.base_path, 'trades', 'trades_history.json')
        trades = self._load_json(filepath, [])
        if limit:
            return trades[-limit:]
        return trades
    
    # ========== Patterns ==========
    def save_pattern(self, pattern_data):
        filepath = os.path.join(self.base_path, 'learning', 'learned_patterns.json')
        patterns = self._load_json(filepath, [])
        pattern_data['last_updated'] = datetime.now().isoformat()
        patterns.append(pattern_data)
        return self._save_json(filepath, patterns)
    
    def load_patterns(self):
        filepath = os.path.join(self.base_path, 'learning', 'learned_patterns.json')
        return self._load_json(filepath, [])
    
    # ========== AI Decisions ==========
    def save_ai_decision(self, decision_data):
        filepath = os.path.join(self.base_path, 'learning', 'ai_decisions.json')
        decisions = self._load_json(filepath, [])
        decision_data['timestamp'] = datetime.now().isoformat()
        decisions.append(decision_data)
        # نحتفظ بآخر 100 قرار فقط
        if len(decisions) > 100:
            decisions = decisions[-100:]
        return self._save_json(filepath, decisions)
    
    def save_learning_data(self, learning_type, data):
        """حفظ بيانات التعلم (الملك والمستشارين)"""
        filepath = os.path.join(self.base_path, 'learning', f'{learning_type}_learning.json')
        existing = self._load_json(filepath, {})
        if isinstance(existing, dict):
            # دمج البيانات
            for key, value in data.items():
                if isinstance(value, dict) and key in existing:
                    for k, v in value.items():
                        if isinstance(v, int) and k in existing[key]:
                            existing[key][k] += v
                        else:
                            existing[key][k] = v
                else:
                    existing[key] = value
            return self._save_json(filepath, existing)
        return self._save_json(filepath, data)
    
    def load_learning_data(self, learning_type):
        """تحميل بيانات التعلم"""
        filepath = os.path.join(self.base_path, 'learning', f'{learning_type}_learning.json')
        return self._load_json(filepath, {})
    
    def load_ai_decisions(self, limit=10):
        filepath = os.path.join(self.base_path, 'learning', 'ai_decisions.json')
        decisions = self._load_json(filepath, [])
        return decisions[-limit:]
    
    # ========== Performance ==========
    def save_performance(self, metrics_data):
        filepath = os.path.join(self.base_path, 'performance', 'daily_metrics.json')
        metrics = self._load_json(filepath, [])
        metrics_data['date'] = datetime.now().strftime('%Y-%m-%d')
        metrics.append(metrics_data)
        return self._save_json(filepath, metrics)
    
    def load_performance(self, days=7):
        filepath = os.path.join(self.base_path, 'performance', 'daily_metrics.json')
        metrics = self._load_json(filepath, [])
        return metrics[-days:]
    
    # ========== Traps ==========
    def save_trap(self, trap_data):
        filepath = os.path.join(self.base_path, 'learning', 'trap_memory.json')
        traps = self._load_json(filepath, [])
        trap_data['timestamp'] = datetime.now().isoformat()
        traps.append(trap_data)
        return self._save_json(filepath, traps)
    
    def load_traps(self):
        filepath = os.path.join(self.base_path, 'learning', 'trap_memory.json')
        return self._load_json(filepath, [])
    
    # ========== Rescue Data (Crazy Trainer) ==========
    def save_rescue_event(self, rescue_data):
        filepath = os.path.join(self.base_path, 'learning', 'rescue_events.json')
        events = self._load_json(filepath, [])
        rescue_data['timestamp'] = datetime.now().isoformat()
        events.append(rescue_data)
        return self._save_json(filepath, events)
    
    # ========== Positions (متوافق مع storage.py الحالي) ==========
    def save_positions(self, positions):
        filepath = os.path.join(self.base_path, 'position.json')
        data = {}
        for symbol, config in positions.items():
            if config.get('position'):
                data[symbol] = config['position']
        return self._save_json(filepath, data)
    
    def load_positions(self):
        filepath = os.path.join(self.base_path, 'position.json')
        return self._load_json(filepath, {})

    def delete_position(self, symbol):
        """Deletes a position from the position.json file."""
        filepath = os.path.join(self.base_path, 'position.json')
        positions = self._load_json(filepath, {})
        if symbol in positions:
            del positions[symbol]
            return self._save_json(filepath, positions)
        return True # Return True even if not found, as the state is correct
