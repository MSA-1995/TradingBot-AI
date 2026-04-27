"""
👑 Meta Package
الواجهة الخارجية - باقي الكود يستورد من هنا بدون تغيير
"""

from meta.meta_core import Meta

# ✅ باقي الكود يستورد نفس الطريقة القديمة
# from meta import Meta  ← يشتغل بدون تغيير

__all__ = ['Meta']