"""
🔌 ML Client - Interface for Trading Bot
Reads ML predictions from database
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote
from datetime import datetime, timedelta

class MLClient:
    def __init__(self, database_url):
        self.database_url = database_url
        self.conn = self._connect_db()
        self.cache = None
        self.cache_time = None
        self.cache_duration = 120  # دقيقتين - تحسين السرعة
    
    def _connect_db(self):
        """Connect to PostgreSQL"""
        try:
            parsed = urlparse(self.database_url)
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],
                user=parsed.username,
                password=unquote(parsed.password)
            )
            return conn
        except Exception as e:
            print(f"❌ ML Client DB error: {e}")
            return None
    
    def is_model_available(self):
        """Check if ML model is trained and available"""
        if not self.conn:
            return False
        
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM ml_predictions
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """)
            result = cursor.fetchone()
            cursor.close()
            
            return result['count'] > 0
        except:
            return False
    
    def get_confidence_adjustment(self, rsi, macd, volume_ratio, momentum, confidence):
        """
        Get ML confidence adjustment for a trade
        Returns: adjustment value (-10 to +10)
        """
        if not self.conn:
            return 0
        
        # Use cache if available
        now = datetime.now()
        if self.cache and self.cache_time:
            if (now - self.cache_time).total_seconds() < self.cache_duration:
                return self._calculate_adjustment(rsi, macd, volume_ratio, momentum, confidence)
        
        # Refresh cache
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT predictions, model_accuracy
                FROM ml_predictions
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                self.cache = result
                self.cache_time = now
                return self._calculate_adjustment(rsi, macd, volume_ratio, momentum, confidence)
            else:
                return 0
        
        except Exception as e:
            return 0
    
    def _calculate_adjustment(self, rsi, macd, volume_ratio, momentum, confidence):
        """
        Calculate confidence adjustment based on ML model
        This is a simplified version - actual prediction would use the trained model
        """
        # Simple heuristic-based adjustment (placeholder)
        # In production, this would load and use the actual model
        
        adjustment = 0
        
        # RSI-based adjustment
        if rsi < 30:
            adjustment += 3  # Oversold = good
        elif rsi > 70:
            adjustment -= 3  # Overbought = bad
        
        # Volume-based adjustment
        if volume_ratio > 2.0:
            adjustment += 2  # High volume = good
        elif volume_ratio < 0.5:
            adjustment -= 2  # Low volume = bad
        
        # Confidence-based adjustment
        if confidence >= 70:
            adjustment += 2  # High confidence = boost
        elif confidence < 60:
            adjustment -= 1  # Low confidence = reduce
        
        # Cap adjustment
        adjustment = max(-10, min(10, adjustment))
        
        return adjustment
    
    def get_model_info(self):
        """Get ML model information"""
        if not self.conn:
            return None
        
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT predictions, model_accuracy, timestamp
                FROM ml_predictions
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                predictions = result['predictions']
                if isinstance(predictions, str):
                    predictions = json.loads(predictions)
                
                # Check if it's the new ensemble format
                if 'models' in predictions:
                    models = predictions['models']
                    return {
                        'model_type': 'Ensemble (RF + LSTM)',
                        'accuracy': result.get('model_accuracy', 0),
                        'rf_accuracy': models.get('random_forest', {}).get('accuracy', 0),
                        'lstm_accuracy': models.get('lstm', {}).get('accuracy', 0),
                        'ensemble_accuracy': models.get('ensemble', {}).get('accuracy', 0),
                        'trained_at': predictions.get('trained_at', 'Unknown'),
                        'status': predictions.get('status', 'Unknown')
                    }
                else:
                    # Old format (Random Forest only)
                    return {
                        'model_type': predictions.get('model_type', 'Unknown'),
                        'accuracy': result.get('model_accuracy', 0),
                        'trained_at': predictions.get('trained_at', 'Unknown'),
                        'status': predictions.get('status', 'Unknown')
                    }
            return None
        
        except Exception as e:
            return None
