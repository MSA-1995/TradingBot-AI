"""
🧠 Simple Neural Network Builder
بناء وتدريب نموذج ذكاء اصطناعي بسيط
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime

# تثبيت المكتبات إذا مو موجودة
def install_requirements():
    import subprocess
    import sys
    
    required = ['tensorflow', 'scikit-learn']
    for package in required:
        try:
            __import__(package)
        except ImportError:
            print(f"📦 Installing {package}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                         capture_output=True)

install_requirements()

import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pickle

class SimpleAI:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        
    def prepare_data(self, df):
        """
        تحضير البيانات للتدريب
        """
        print("\n📊 Preparing data...")
        
        # Features (المدخلات)
        feature_cols = ['rsi', 'macd_diff', 'volume', 'confidence']
        self.feature_names = feature_cols
        
        X = df[feature_cols].values
        
        # Target (الهدف: ربح أو خسارة)
        y = df['result'].values  # 1=ربح, 0=خسارة
        
        # تنظيف البيانات
        # حذف الصفوف اللي فيها NaN
        mask = ~np.isnan(X).any(axis=1)
        X = X[mask]
        y = y[mask]
        
        print(f"✅ Data prepared: {len(X)} samples")
        print(f"   Features: {feature_cols}")
        print(f"   Winning trades: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
        print(f"   Losing trades: {len(y)-sum(y)} ({(len(y)-sum(y))/len(y)*100:.1f}%)")
        
        return X, y
    
    def build_model(self, input_shape):
        """
        بناء Neural Network
        """
        print("\n🏗️ Building Neural Network...")
        
        model = keras.Sequential([
            # Input layer
            keras.layers.Dense(32, activation='relu', input_shape=(input_shape,)),
            keras.layers.Dropout(0.3),  # منع Overfitting
            
            # Hidden layer
            keras.layers.Dense(16, activation='relu'),
            keras.layers.Dropout(0.2),
            
            # Output layer (BUY or SKIP)
            keras.layers.Dense(1, activation='sigmoid')  # 0-1 احتمال
        ])
        
        # Compile
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        print("✅ Model built:")
        model.summary()
        
        self.model = model
        return model
    
    def train(self, X, y, epochs=50, validation_split=0.2):
        """
        تدريب النموذج
        """
        print(f"\n🎓 Training model ({epochs} epochs)...")
        
        # تقسيم البيانات
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Normalize البيانات
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)
        
        # التدريب
        history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=16,
            validation_split=validation_split,
            verbose=1
        )
        
        # التقييم
        print("\n📊 Evaluating model...")
        test_loss, test_accuracy = self.model.evaluate(X_test, y_test, verbose=0)
        
        print(f"\n✅ Training completed!")
        print(f"   Test Accuracy: {test_accuracy*100:.2f}%")
        print(f"   Test Loss: {test_loss:.4f}")
        
        # تحليل النتائج
        predictions = self.model.predict(X_test, verbose=0)
        predicted_classes = (predictions > 0.5).astype(int).flatten()
        
        # حساب Win Rate للتنبؤات
        correct_predictions = (predicted_classes == y_test).sum()
        print(f"   Correct Predictions: {correct_predictions}/{len(y_test)}")
        
        # True Positives (تنبأ بربح وفعلاً ربح)
        true_positives = ((predicted_classes == 1) & (y_test == 1)).sum()
        predicted_wins = (predicted_classes == 1).sum()
        if predicted_wins > 0:
            precision = true_positives / predicted_wins
            print(f"   Precision (when predicts WIN): {precision*100:.1f}%")
        
        return history, test_accuracy
    
    def predict(self, features):
        """
        التنبؤ بصفقة جديدة
        
        features: [rsi, macd_diff, volume, confidence]
        Returns: probability (0-1)
        """
        # Normalize
        features_scaled = self.scaler.transform([features])
        
        # Predict
        probability = self.model.predict(features_scaled, verbose=0)[0][0]
        
        return float(probability)
    
    def save(self, model_path='simple_ai_model.h5', scaler_path='scaler.pkl'):
        """
        حفظ النموذج
        """
        print(f"\n💾 Saving model...")
        
        # حفظ النموذج
        self.model.save(model_path)
        
        # حفظ Scaler
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        # حفظ Feature names
        with open('feature_names.pkl', 'wb') as f:
            pickle.dump(self.feature_names, f)
        
        print(f"✅ Model saved:")
        print(f"   - {model_path}")
        print(f"   - {scaler_path}")
        print(f"   - feature_names.pkl")
    
    def load(self, model_path='simple_ai_model.h5', scaler_path='scaler.pkl'):
        """
        تحميل النموذج
        """
        print(f"\n📂 Loading model...")
        
        # تحميل النموذج
        self.model = keras.models.load_model(model_path)
        
        # تحميل Scaler
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)
        
        # تحميل Feature names
        with open('feature_names.pkl', 'rb') as f:
            self.feature_names = pickle.load(f)
        
        print(f"✅ Model loaded successfully")
        return self
    
    def test_prediction(self, sample_data):
        """
        اختبار التنبؤ على بيانات عينة
        """
        print("\n🧪 Testing predictions...")
        
        for i, row in sample_data.iterrows():
            features = [row['rsi'], row['macd_diff'], row['volume'], row['confidence']]
            probability = self.predict(features)
            actual = "WIN" if row['result'] == 1 else "LOSS"
            predicted = "BUY" if probability > 0.7 else "SKIP"
            
            print(f"\n  Sample {i+1}:")
            print(f"    RSI: {row['rsi']:.1f} | MACD: {row['macd_diff']:.1f} | Vol: {row['volume']:.2f} | Conf: {row['confidence']:.0f}")
            print(f"    Actual: {actual} | Predicted: {predicted} ({probability*100:.1f}% confidence)")


# ========== MAIN ==========
if __name__ == "__main__":
    print("="*60)
    print("🧠 SIMPLE AI TRAINING")
    print("="*60)
    
    # 1. تحميل البيانات
    from data_loader import DataLoader
    
    loader = DataLoader()
    df = loader.load_trades_for_training()
    
    if df is None or len(df) < 50:
        print("\n❌ Not enough data for training!")
        print("   Need at least 50 trades")
        print("   Run the bot for a few days to collect more data")
        exit()
    
    # عرض الإحصائيات
    loader.print_statistics(df)
    
    # 2. بناء وتدريب النموذج
    ai = SimpleAI()
    
    # تحضير البيانات
    X, y = ai.prepare_data(df)
    
    # بناء النموذج
    ai.build_model(input_shape=X.shape[1])
    
    # التدريب
    history, accuracy = ai.train(X, y, epochs=50)
    
    # 3. حفظ النموذج
    ai.save()
    
    # 4. اختبار على عينات
    print("\n" + "="*60)
    print("🧪 TESTING ON SAMPLE DATA")
    print("="*60)
    
    sample = df.sample(min(5, len(df)))
    ai.test_prediction(sample)
    
    print("\n" + "="*60)
    print("✅ TRAINING COMPLETED!")
    print("="*60)
    print("\nNext steps:")
    print("1. Check the accuracy (should be > 60%)")
    print("2. If good, integrate with trading_bot.py")
    print("3. If bad, collect more data and retrain")
    print("\nFiles created:")
    print("  - simple_ai_model.h5 (the brain)")
    print("  - scaler.pkl (data normalizer)")
    print("  - feature_names.pkl (feature list)")
    
    loader.close()
