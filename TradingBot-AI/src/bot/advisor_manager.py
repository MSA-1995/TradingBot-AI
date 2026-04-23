# src/bot/advisor_manager.py - السكرتير الذكي (نظام التحميل عند الطلب)
import time
from threading import Lock
import sys
import os

# إضافة المسار الجذر (TradingBot-AI) إلى مسارات بايثون
current_dir  = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
src_path     = os.path.join(project_root, 'src')
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from dl_client_v2 import DeepLearningClientV2
from news_analyzer import NewsAnalyzer

# استيراد النماذج من مجلد models (الثابتة فقط - غير المدربة)
sys.path.insert(0, os.path.join(project_root, 'models'))
from fibonacci_analyzer import FibonacciAnalyzer
from macro_trend_advisor import MacroTrendAdvisor
from adaptive_intelligence import AdaptiveIntelligence
from liquidation_shield import LiquidationShield
from volume_forecast_engine import VolumeForecastEngine
from trend_early_detector import TrendEarlyDetector

class AdvisorManager:
    """
    يقوم هذا الكلاس بتطبيق نمط "التحميل الكسول" (Lazy Loading).
    لا يتم تحميل أي مستشار في الذاكرة عند بدء التشغيل.
    يتم إنشاء وتخزين المستشار فقط عند طلبه لأول مرة.
    """
    _lock     = Lock()
    _advisors = {}  # Shared by all instances of this class

    def __init__(self, storage, capital_manager, exchange=None, dl_client=None):
        if dl_client and 'dl_client' not in self.__class__._advisors:
            self.__class__._advisors['dl_client']              = dl_client
            self.__class__._advisors['DeepLearningClientV2']   = dl_client

        self._storage          = storage
        self._capital_manager  = capital_manager
        self._exchange         = exchange

        self._creators = {
            'DeepLearningClientV2': lambda: DeepLearningClientV2(database_url=os.getenv('DATABASE_URL')) if os.getenv('DATABASE_URL') else None,
            'dl_client':            lambda: DeepLearningClientV2(database_url=os.getenv('DATABASE_URL')) if os.getenv('DATABASE_URL') else None,

            # ✅ النماذج المدربة (من قاعدة البيانات عبر dl_client)
            'RiskManager':                  lambda: self._create_ai_advisor('risk'),
            'ExitStrategyModel':            lambda: self._create_ai_advisor('exit'),
            'AnomalyDetector':              lambda: self._create_ai_advisor('anomaly'),
            'LiquidityAnalyzer':            lambda: self._create_ai_advisor('liquidity'),
            'EnhancedPatternRecognition':   lambda: self._create_ai_advisor('pattern'),
            'SmartMoneyTracker':            lambda: self._create_ai_advisor('smart_money'),

            # النماذج الثابتة (غير مدربة - تبقى كما هي)
            'FibonacciAnalyzer':    lambda: FibonacciAnalyzer(),
            'NewsAnalyzer':         lambda: NewsAnalyzer(self._storage),
            'MacroTrendAdvisor':    lambda: MacroTrendAdvisor(self._exchange),

            # الأنظمة الحصرية الـ 5
            'AdaptiveIntelligence': lambda: AdaptiveIntelligence(self._storage),
            'LiquidationShield':    lambda: LiquidationShield(),
            'VolumeForecastEngine': lambda: VolumeForecastEngine(),
            'TrendEarlyDetector':   lambda: TrendEarlyDetector(),
        }
        print("✅ AdvisorManager is initialized and ready for on-demand loading.")

    def _create_ai_advisor(self, model_name):
        """
        ✅ إنشاء مستشار ذكي يستخدم النموذج المدرب من قاعدة البيانات
        بدلاً من الكود الثابت
        """
        try:
            dl_client = self.get('dl_client')
            if not dl_client:
                print(f"⚠️ AI Advisor '{model_name}': dl_client not available, using fallback")
                return AIAdvisorWrapper(model_name, None, self._storage, self._exchange)

            model = dl_client._models.get(model_name) if hasattr(dl_client, '_models') else None
            if not model:
                print(f"⚠️ AI Advisor '{model_name}': Model not trained yet, using fallback")
                return AIAdvisorWrapper(model_name, None, self._storage, self._exchange)

            print(f"✅ AI Advisor '{model_name}': Using trained model from database")
            return AIAdvisorWrapper(model_name, dl_client, self._storage, self._exchange)

        except Exception as e:
            print(f"❌ Error creating AI advisor '{model_name}': {e}")
            return AIAdvisorWrapper(model_name, None, self._storage, self._exchange)

    def get(self, advisor_name):
        """
        يستدعي المستشار عند الطلب.
        إذا لم يكن المستشار موجودًا، يتم إنشاؤه وتخزينه.
        """
        if advisor_name not in self.__class__._advisors:
            with self.__class__._lock:
                if advisor_name not in self.__class__._advisors:
                    if advisor_name in self._creators:
                        self.__class__._advisors[advisor_name] = self._creators[advisor_name]()
                    else:
                        print(f"⚠️ AdvisorManager: المستشار '{advisor_name}' غير معروف")
                        return None

        return self.__class__._advisors.get(advisor_name)


class AIAdvisorWrapper:
    """
    ✅ Wrapper للنماذج المدربة - يوفر نفس الواجهة للنماذج القديمة
    لكن يستخدم الذكاء الاصطناعي المدرب بدلاً من الكود الثابت
    """
    def __init__(self, model_name, dl_client, storage, exchange):
        self.model_name       = model_name
        self.dl_client        = dl_client
        self.storage          = storage
        self.exchange         = exchange
        self.has_trained_model = dl_client is not None

    def get_confidence_adjustment(self, symbol, analysis):
        """للنماذج التي تعطي تعديل ثقة (SmartMoneyTracker, RiskManager)"""
        if not self.has_trained_model:
            return 0

        try:
            advice = self.dl_client.get_advice(
                rsi=analysis.get('rsi', 50),
                macd=analysis.get('macd_diff', 0),
                volume_ratio=analysis.get('volume_ratio', 1.0),
                price_momentum=analysis.get('price_momentum', 0),
                confidence=50,
                analysis_data=analysis,
                action='BUY'
            )

            model_advice = advice.get(self.model_name, 'Neutral')

            if 'Strong-Bullish' in str(model_advice):   return 15
            elif 'Bullish' in str(model_advice):         return 8
            elif 'Strong-Bearish' in str(model_advice):  return -15
            elif 'Bearish' in str(model_advice):         return -8
            else:                                        return 0

        except Exception as e:
            print(f"⚠️ AI Advisor error ({self.model_name}): {e}")
            return 0

    def should_exit(self, symbol, position, current_price, analysis, mtf):
        """لنموذج ExitStrategyModel"""
        buy_price = float(position.get('buy_price', 0) or 0)
        profit    = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

        if not self.has_trained_model:
            if profit > 5:
                return {'action': 'SELL', 'reason': 'Simple profit target', 'profit': profit}
            return {'action': 'HOLD', 'reason': 'Waiting', 'profit': profit}

        try:
            advice = self.dl_client.get_advice(
                rsi=analysis.get('rsi', 50),
                macd=analysis.get('macd_diff', 0),
                volume_ratio=analysis.get('volume_ratio', 1.0),
                price_momentum=analysis.get('price_momentum', 0),
                confidence=50,
                analysis_data=analysis,
                action='SELL'
            )

            exit_advice = advice.get('exit', 'Neutral')

            if 'Strong-Bearish' in str(exit_advice) and profit > 0.5:
                return {'action': 'SELL', 'reason': f'AI Exit: {exit_advice}', 'profit': profit}
            elif 'Bearish' in str(exit_advice) and profit > 2:
                return {'action': 'SELL', 'reason': f'AI Exit: {exit_advice}', 'profit': profit}
            else:
                return {'action': 'HOLD', 'reason': f'AI: {exit_advice}', 'profit': profit}

        except Exception as e:
            print(f"⚠️ AI Exit error: {e}")
            return {'action': 'HOLD', 'reason': 'Error', 'profit': profit}

    def detect_anomalies(self, symbol, analysis):
        """لنموذج AnomalyDetector"""
        if not self.has_trained_model:
            return {
                'symbol': symbol, 'anomalies': [],
                'severity': 'NORMAL', 'anomaly_score': 0, 'safe_to_trade': True
            }

        try:
            advice = self.dl_client.get_advice(
                rsi=analysis.get('rsi', 50),
                macd=analysis.get('macd_diff', 0),
                volume_ratio=analysis.get('volume_ratio', 1.0),
                price_momentum=analysis.get('price_momentum', 0),
                confidence=50,
                analysis_data=analysis,
                action='BUY'
            )

            anomaly_advice = advice.get('anomaly', 'Neutral')

            if 'Strong-Bearish' in str(anomaly_advice):
                return {
                    'symbol': symbol,
                    'anomalies': [{'type': 'AI_DETECTED', 'risk': 'HIGH'}],
                    'severity': 'HIGH', 'anomaly_score': 80, 'safe_to_trade': False
                }
            elif 'Bearish' in str(anomaly_advice):
                return {
                    'symbol': symbol,
                    'anomalies': [{'type': 'AI_DETECTED', 'risk': 'MEDIUM'}],
                    'severity': 'MEDIUM', 'anomaly_score': 50, 'safe_to_trade': True
                }
            else:
                return {
                    'symbol': symbol, 'anomalies': [],
                    'severity': 'NORMAL', 'anomaly_score': 0, 'safe_to_trade': True
                }

        except Exception as e:
            print(f"⚠️ AI Anomaly error: {e}")
            return {
                'symbol': symbol, 'anomalies': [],
                'severity': 'NORMAL', 'anomaly_score': 0, 'safe_to_trade': True
            }

    def analyze_entry_pattern(self, symbol, analysis, mtf, price_drop):
        """لنموذج EnhancedPatternRecognition"""
        if not self.has_trained_model:
            return {
                'success_probability': 0.5, 'pattern_strength': 'WEAK',
                'recommendation': 'NEUTRAL', 'confidence_adjustment': 0
            }

        try:
            advice = self.dl_client.get_advice(
                rsi=analysis.get('rsi', 50),
                macd=analysis.get('macd_diff', 0),
                volume_ratio=analysis.get('volume_ratio', 1.0),
                price_momentum=analysis.get('price_momentum', 0),
                confidence=50,
                analysis_data=analysis,
                action='BUY'
            )

            pattern_advice = advice.get('pattern', 'Neutral')

            if 'Strong-Bullish' in str(pattern_advice):
                return {
                    'success_probability': 0.8, 'pattern_strength': 'STRONG',
                    'recommendation': 'STRONG_BUY', 'confidence_adjustment': 10
                }
            elif 'Bullish' in str(pattern_advice):
                return {
                    'success_probability': 0.65, 'pattern_strength': 'MEDIUM',
                    'recommendation': 'BUY', 'confidence_adjustment': 5
                }
            else:
                return {
                    'success_probability': 0.5, 'pattern_strength': 'WEAK',
                    'recommendation': 'NEUTRAL', 'confidence_adjustment': 0
                }

        except Exception as e:
            print(f"⚠️ AI Pattern error: {e}")
            return {
                'success_probability': 0.5, 'pattern_strength': 'WEAK',
                'recommendation': 'NEUTRAL', 'confidence_adjustment': 0
            }

    def calculate_liquidity_score(self, symbol, analysis):
        """لنموذج LiquidityAnalyzer"""
        if not self.has_trained_model:
            return 50

        try:
            advice = self.dl_client.get_advice(
                rsi=analysis.get('rsi', 50),
                macd=analysis.get('macd_diff', 0),
                volume_ratio=analysis.get('volume_ratio', 1.0),
                price_momentum=analysis.get('price_momentum', 0),
                confidence=50,
                liquidity_metrics=analysis.get('liquidity_metrics'),
                analysis_data=analysis,
                action='BUY'
            )

            liquidity_advice = advice.get('liquidity', 'Neutral')

            if 'Strong-Bullish' in str(liquidity_advice):   return 90
            elif 'Bullish' in str(liquidity_advice):         return 70
            elif 'Strong-Bearish' in str(liquidity_advice):  return 20
            elif 'Bearish' in str(liquidity_advice):         return 40
            else:                                            return 50

        except Exception as e:
            print(f"⚠️ AI Liquidity error: {e}")
            return 50

    def calculate_optimal_amount(self, symbol, confidence, base_amount=12, max_amount=700, whale_confidence=0):
        """لنموذج RiskManager"""
        try:
            if confidence >= 90:   multiplier = 1.0
            elif confidence >= 80: multiplier = 0.8
            elif confidence >= 70: multiplier = 0.6
            else:                  multiplier = 0.4

            optimal = base_amount + (max_amount - base_amount) * multiplier
            return max(base_amount, min(optimal, max_amount))

        except Exception as e:
            print(f"⚠️ AI Risk error: {e}")
            return base_amount