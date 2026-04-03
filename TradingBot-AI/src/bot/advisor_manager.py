# src/bot/advisor_manager.py - السكرتير الذكي (نظام التحميل عند الطلب)
import time
from threading import Lock
import sys
import os

# إضافة المسار الجذر (TradingBot-AI) إلى مسارات بايثون
# هذا يسمح باستيراد الوحدات من أي مكان في المشروع
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from src.dl_client_v2 import DeepLearningClientV2
from models.risk_manager import RiskManager
from models.exit_strategy_model import ExitStrategyModel
from models.anomaly_detector import AnomalyDetector

from models.liquidity_analyzer import LiquidityAnalyzer
from models.enhanced_pattern_recognition import EnhancedPatternRecognition
from models.smart_money_tracker import SmartMoneyTracker
from models.fibonacci_analyzer import FibonacciAnalyzer
from src.news_analyzer import NewsAnalyzer # استخدام النسخة من src

class AdvisorManager:
    _lock = Lock()
    _advisors = {}  # Shared by all instances of this class
    """
    يقوم هذا الكلاس بتطبيق نمط "التحميل الكسول" (Lazy Loading).
    لا يتم تحميل أي مستشار في الذاكرة عند بدء التشغيل.
    يتم إنشاء وتخزين المستشار فقط عند طلبه لأول مرة.
    """
    def __init__(self, storage, capital_manager, exchange=None, dl_client=None):
        # self._advisors is now a class variable, no need to initialize it here.
        # self.instance_id = uuid.uuid4() # <<< No longer needed for diagnostics

        # إذا تم تمرير dl_client جاهز، نقوم بتخزينه مباشرة في المتغير المشترك
        if dl_client and 'dl_client' not in self.__class__._advisors:
            self.__class__._advisors['dl_client'] = dl_client
            
        self._creators = {
            'DeepLearningClientV2': lambda: DeepLearningClientV2(database_url=os.getenv('DATABASE_URL')) if os.getenv('DATABASE_URL') else None,
            'dl_client': lambda: DeepLearningClientV2(database_url=os.getenv('DATABASE_URL')) if os.getenv('DATABASE_URL') else None, # اسم بديل
            'RiskManager': lambda: RiskManager(storage),
            'ExitStrategyModel': lambda: ExitStrategyModel(storage),
            'AnomalyDetector': lambda: AnomalyDetector(storage),

            'LiquidityAnalyzer': lambda: LiquidityAnalyzer(exchange), # <<< إضافة exchange
            'EnhancedPatternRecognition': lambda: EnhancedPatternRecognition(storage), # <<< إضافة storage
            'SmartMoneyTracker': lambda: SmartMoneyTracker(exchange), # <<< إضافة exchange
            'FibonacciAnalyzer': lambda: FibonacciAnalyzer(),
            'NewsAnalyzer': lambda: NewsAnalyzer(),
        }
        self._storage = storage
        self._capital_manager = capital_manager
        self._exchange = exchange
        # No instance lock needed, we use the class lock
        print("✅ AdvisorManager is initialized and ready for on-demand loading.")

    def get(self, advisor_name):
        """
        يستدعي المستشار عند الطلب.
        إذا لم يكن المستشار موجودًا، يتم إنشاؤه وتخزينه.
        """
        # Double-checked locking: first check without the lock for performance
        if advisor_name not in self.__class__._advisors:
            # Use the class-level lock to ensure thread safety
            with self.__class__._lock:
                # Second check inside the lock to ensure thread safety
                if advisor_name not in self.__class__._advisors:
                    if advisor_name in self._creators:
                        self.__class__._advisors[advisor_name] = self._creators[advisor_name]()
                    else:
                        # هذا بمثابة إجراء أمان، لا يجب أن يحدث في الحالة الطبيعية
                        raise ValueError(f"خطأ فادح: المستشار '{advisor_name}' غير معروف!")

        return self.__class__._advisors[advisor_name]
