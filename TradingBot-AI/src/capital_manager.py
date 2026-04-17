"""
💰 Capital Manager
يدير رأس المال ويحفظ الأرباح
"""

class CapitalManager:
    def __init__(self, max_capital=300, profit_reserve=True):
        """
        max_capital: الحد الأقصى لرأس المال المستخدم ($200-$300)
        profit_reserve: حفظ الأرباح (لا يتداول فيها)
        """
        self.max_capital = max_capital
        self.profit_reserve = profit_reserve
        self.initial_capital = None  # يتم تحديده أول مرة
        self.total_profit = 0
    
    def get_tradable_balance(self, current_balance, invested):
        """
        حساب الرصيد القابل للتداول
        
        Returns:
            tradable: الرصيد المتاح للتداول
            locked_profit: الأرباح المحفوظة
            status: حالة رأس المال
        """
        # أول مرة - تحديد رأس المال الأولي
        if self.initial_capital is None:
            self.initial_capital = min(current_balance, self.max_capital)
        
        # إجمالي رأس المال الحالي
        total_capital = current_balance + invested
        
        # حساب الأرباح
        profit = total_capital - self.initial_capital
        
        if not self.profit_reserve:
            # لا يوجد حفظ أرباح - كل الرصيد متاح
            return {
                'tradable': current_balance,
                'locked_profit': 0,
                'total_profit': profit,
                'status': 'FULL_TRADING'
            }
        
        # حفظ الأرباح
        if profit > 0:
            # الأرباح محفوظة
            locked_profit = profit
            
            # رأس المال المتاح = الأولي - المستثمر
            available_capital = self.initial_capital - invested
            
            # الرصيد القابل للتداول = الأقل بين (الرصيد الحالي، رأس المال المتاح)
            tradable = min(current_balance, max(0, available_capital))
            
            return {
                'tradable': tradable,
                'locked_profit': locked_profit,
                'total_profit': profit,
                'status': 'PROFIT_LOCKED'
            }
        else:
            # لا توجد أرباح بعد
            # رأس المال المتاح = الحد الأقصى - المستثمر
            available_capital = self.max_capital - invested
            
            # الرصيد القابل للتداول
            tradable = min(current_balance, max(0, available_capital))
            
            return {
                'tradable': tradable,
                'locked_profit': 0,
                'total_profit': profit,
                'status': 'BUILDING_CAPITAL'
            }
    
    def can_trade(self, amount, current_balance, invested):
        """
        هل يمكن فتح صفقة بهذا المبلغ؟
        """
        result = self.get_tradable_balance(current_balance, invested)
        
        # فحص 1: هل الرصيد القابل للتداول كافي؟
        if result['tradable'] < amount:
            return False, f"Tradable balance ${result['tradable']:.2f} < ${amount}"
        
        # فحص 2: هل سيتجاوز الحد الأقصى؟
        new_invested = invested + amount
        if new_invested > self.max_capital:
            return False, f"Would exceed max capital ${self.max_capital}"
        
        return True, "OK"
    
    def get_status_display(self, current_balance, invested):
        """
        عرض حالة رأس المال
        """
        result = self.get_tradable_balance(current_balance, invested)
        
        total_capital = current_balance + invested
        
        lines = []
        lines.append(f"💰 Capital Status:")
        lines.append(f"  Initial: ${self.initial_capital:.2f}")
        lines.append(f"  Current: ${total_capital:.2f}")
        lines.append(f"  Max: ${self.max_capital}")
        lines.append(f"  Profit: ${result['total_profit']:+.2f}")
        
        if self.profit_reserve and result['locked_profit'] > 0:
            lines.append(f"  🔒 Locked Profit: ${result['locked_profit']:.2f}")
            lines.append(f"  ✅ Tradable: ${result['tradable']:.2f}")
        else:
            lines.append(f"  ✅ Tradable: ${result['tradable']:.2f}")
        
        lines.append(f"  Status: {result['status']}")
        
        return "\n".join(lines)
