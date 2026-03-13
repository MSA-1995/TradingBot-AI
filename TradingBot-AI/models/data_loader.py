"""
📊 Data Loader - قراءة البيانات من Database
يحضر البيانات للتدريب
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, unquote

class DataLoader:
    def __init__(self):
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            raise Exception("❌ DATABASE_URL not found!")
        
        # الاتصال بالـ Database
        parsed = urlparse(database_url)
        self.conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=unquote(parsed.password)
        )
        print("✅ Connected to Database")
    
    def load_trades_for_training(self):
        """
        قراءة جميع الصفقات من Database
        Returns: DataFrame جاهز للتدريب
        """
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            
            # قراءة كل الصفقات
            cursor.execute("""
                SELECT * FROM trades_history 
                ORDER BY timestamp DESC
            """)
            
            trades = cursor.fetchall()
            cursor.close()
            
            if not trades:
                print("⚠️ No trades found in database!")
                return None
            
            print(f"📊 Loaded {len(trades)} trades from database")
            
            # تحويل لـ DataFrame
            df = pd.DataFrame(trades)
            
            # استخراج البيانات من JSON
            df = self._extract_features(df)
            
            # تنظيف البيانات
            df = self._clean_data(df)
            
            print(f"✅ Prepared {len(df)} trades for training")
            print(f"   Features: {df.columns.tolist()}")
            
            return df
            
        except Exception as e:
            print(f"❌ Error loading trades: {e}")
            return None
    
    def _extract_features(self, df):
        """
        استخراج المعلومات من JSON data
        """
        try:
            # استخراج البيانات من عمود data
            if 'data' in df.columns:
                import json
                
                features = []
                for idx, row in df.iterrows():
                    try:
                        data = row['data']
                        if isinstance(data, str):
                            data = json.loads(data)
                        
                        # استخراج المعلومات المهمة
                        feature = {
                            'symbol': row.get('symbol', 'UNKNOWN'),
                            'action': row.get('action', 'UNKNOWN'),
                            'profit_percent': row.get('profit_percent', 0),
                            'sell_reason': row.get('sell_reason', 'UNKNOWN'),
                            'hours_held': row.get('hours_held', 24),
                            
                            # من data
                            'rsi': data.get('rsi', 50),
                            'macd_diff': data.get('macd_diff', 0),
                            'volume': data.get('volume', 1),
                            'confidence': data.get('confidence', 60),
                            
                            # الهدف (النتيجة)
                            'result': 1 if row.get('profit_percent', 0) > 0 else 0  # 1=ربح, 0=خسارة
                        }
                        
                        features.append(feature)
                    except Exception as e:
                        print(f"⚠️ Error extracting row {idx}: {e}")
                        continue
                
                df = pd.DataFrame(features)
            
            return df
            
        except Exception as e:
            print(f"❌ Error extracting features: {e}")
            return df
    
    def _clean_data(self, df):
        """
        تنظيف البيانات
        """
        try:
            # حذف الصفوف الفارغة
            df = df.dropna()
            
            # تحويل الأنواع
            numeric_cols = ['profit_percent', 'hours_held', 'rsi', 'macd_diff', 'volume', 'confidence']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # حذف القيم الشاذة
            df = df[df['rsi'].between(0, 100)]
            df = df[df['volume'] > 0]
            df = df[df['confidence'].between(0, 120)]
            
            # حذف الصفوف الفارغة بعد التنظيف
            df = df.dropna()
            
            return df
            
        except Exception as e:
            print(f"❌ Error cleaning data: {e}")
            return df
    
    def get_statistics(self, df):
        """
        إحصائيات البيانات
        """
        if df is None or len(df) == 0:
            return None
        
        stats = {
            'total_trades': len(df),
            'winning_trades': len(df[df['result'] == 1]),
            'losing_trades': len(df[df['result'] == 0]),
            'win_rate': len(df[df['result'] == 1]) / len(df) * 100,
            'avg_profit': df[df['result'] == 1]['profit_percent'].mean(),
            'avg_loss': df[df['result'] == 0]['profit_percent'].mean(),
            'avg_hours_held': df['hours_held'].mean(),
            
            # توزيع العملات
            'top_symbols': df['symbol'].value_counts().head(5).to_dict(),
            
            # توزيع RSI
            'avg_rsi': df['rsi'].mean(),
            'avg_volume': df['volume'].mean(),
            'avg_confidence': df['confidence'].mean()
        }
        
        return stats
    
    def print_statistics(self, df):
        """
        طباعة الإحصائيات
        """
        stats = self.get_statistics(df)
        
        if not stats:
            print("❌ No statistics available")
            return
        
        print("\n" + "="*60)
        print("📊 DATA STATISTICS")
        print("="*60)
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Winning: {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
        print(f"Losing: {stats['losing_trades']} ({100-stats['win_rate']:.1f}%)")
        print(f"\nAvg Profit: {stats['avg_profit']:.2f}%")
        print(f"Avg Loss: {stats['avg_loss']:.2f}%")
        print(f"Avg Hours Held: {stats['avg_hours_held']:.1f}h")
        print(f"\nAvg RSI: {stats['avg_rsi']:.1f}")
        print(f"Avg Volume: {stats['avg_volume']:.2f}x")
        print(f"Avg Confidence: {stats['avg_confidence']:.1f}")
        print(f"\nTop 5 Symbols:")
        for symbol, count in stats['top_symbols'].items():
            print(f"  {symbol}: {count} trades")
        print("="*60 + "\n")
    
    def save_to_csv(self, df, filename='training_data.csv'):
        """
        حفظ البيانات في CSV
        """
        try:
            df.to_csv(filename, index=False)
            print(f"✅ Data saved to {filename}")
            return True
        except Exception as e:
            print(f"❌ Error saving CSV: {e}")
            return False
    
    def close(self):
        """
        إغلاق الاتصال
        """
        if self.conn:
            self.conn.close()
            print("✅ Database connection closed")


# ========== TEST ==========
if __name__ == "__main__":
    print("🚀 Testing Data Loader...\n")
    
    # تحميل البيانات
    loader = DataLoader()
    df = loader.load_trades_for_training()
    
    if df is not None:
        # عرض الإحصائيات
        loader.print_statistics(df)
        
        # عرض عينة من البيانات
        print("📋 Sample Data:")
        print(df.head(10))
        
        # حفظ في CSV
        loader.save_to_csv(df)
    
    loader.close()
