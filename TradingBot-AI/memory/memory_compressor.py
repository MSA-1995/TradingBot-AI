# memory_compressor.py - في الذاكرة فقط

import json
import zlib
from typing import Any, Optional


class MemoryCompressor:
    """يضغط البيانات الكبيرة ويخزنها في الذاكرة فقط"""

    # ─── إعدادات الضغط ───
    COMPRESS_LEVEL_MAX      = 9    # أعلى ضغط للشموع
    COMPRESS_LEVEL_DEFAULT  = 6    # ضغط متوازن
    PARTIAL_THRESHOLD       = 5_000
    MIN_CANDLE_FIELDS       = 6    # [timestamp, open, high, low, close, volume]

    # ─── مفاتيح البيانات الأساسية ───
    ESSENTIAL_ANALYSIS_KEYS = ('signal', 'confidence', 'price')

    # ─── مفاتيح الضغط ───
    KEY_COMPRESSED          = 'compressed'
    KEY_PARTIAL             = 'partial_compressed'
    KEY_ORIGINAL_SIZE       = 'original_size'
    KEY_COMPRESSED_SIZE     = 'compressed_size'
    KEY_RATIO               = 'ratio'

    # ─────────────────────────────────────────────
    # الشموع
    # ─────────────────────────────────────────────

    @staticmethod
    def compress_candles(candles_data: list) -> Optional[dict]:
        """يضغط شموع التحليل في الذاكرة"""
        if not candles_data:
            return None

        try:
            cleaned = [
                [
                    int(c[0]),    # timestamp
                    float(c[1]),  # open
                    float(c[2]),  # high
                    float(c[3]),  # low
                    float(c[4]),  # close
                    float(c[5])   # volume
                ]
                for c in candles_data
                if len(c) >= MemoryCompressor.MIN_CANDLE_FIELDS
            ]

            return MemoryCompressor._compress_to_dict(
                cleaned,
                level=MemoryCompressor.COMPRESS_LEVEL_MAX
            )

        except Exception as e:
            print(f"⚠️ compress_candles error: {e}")
            return None

    @staticmethod
    def decompress_candles(compressed_data: Optional[dict]) -> Optional[list]:
        """يفك ضغط الشموع من الذاكرة"""
        if not compressed_data or MemoryCompressor.KEY_COMPRESSED not in compressed_data:
            return None

        try:
            raw = zlib.decompress(compressed_data[MemoryCompressor.KEY_COMPRESSED])
            return json.loads(raw.decode('utf-8'))
        except Exception as e:
            print(f"⚠️ decompress_candles error: {e}")
            return None

    # ─────────────────────────────────────────────
    # نتائج التحليل
    # ─────────────────────────────────────────────

    @staticmethod
    def compress_analysis_result(analysis_data: dict) -> Optional[dict]:
        """يضغط نتائج التحليل (البيانات الأساسية فقط)"""
        if not analysis_data:
            return None

        try:
            indicators = analysis_data.get('indicators', {})
            essential  = {
                'signal':     analysis_data.get('signal'),
                'confidence': analysis_data.get('confidence'),
                'price':      analysis_data.get('price'),
                'rsi':        indicators.get('rsi'),
                'macd':       indicators.get('macd')
            }

            return MemoryCompressor._compress_to_dict(
                essential,
                level=MemoryCompressor.COMPRESS_LEVEL_DEFAULT
            )

        except Exception as e:
            print(f"⚠️ compress_analysis_result error: {e}")
            return None

    @staticmethod
    def decompress_analysis_result(compressed_data: Optional[dict]) -> Optional[dict]:
        """يفك ضغط نتائج التحليل"""
        if not compressed_data or MemoryCompressor.KEY_COMPRESSED not in compressed_data:
            return None

        try:
            raw = zlib.decompress(compressed_data[MemoryCompressor.KEY_COMPRESSED])
            return json.loads(raw.decode('utf-8'))
        except Exception as e:
            print(f"⚠️ decompress_analysis_result error: {e}")
            return None

    # ─────────────────────────────────────────────
    # ضغط جزئي
    # ─────────────────────────────────────────────

    @staticmethod
    def compress_partial(data: Any,
                          threshold: Optional[int] = None) -> Any:
        """ضغط جزئي للبيانات الكبيرة (يتجاهل الصغيرة)"""
        if threshold is None:
            threshold = MemoryCompressor.PARTIAL_THRESHOLD

        if not data:
            return data

        try:
            data_str = str(data)
            if len(data_str) <= threshold:
                return data

            compressed = zlib.compress(
                data_str.encode('utf-8'),
                level=MemoryCompressor.COMPRESS_LEVEL_DEFAULT
            )
            return {
                MemoryCompressor.KEY_PARTIAL:         compressed,
                MemoryCompressor.KEY_ORIGINAL_SIZE:   len(data_str),
                MemoryCompressor.KEY_COMPRESSED_SIZE: len(compressed),
                MemoryCompressor.KEY_RATIO:           len(compressed) / len(data_str)
            }

        except Exception as e:
            print(f"⚠️ compress_partial error: {e}")
            return data

    @staticmethod
    def decompress_partial(data: Any) -> Any:
        """يفك الضغط الجزئي"""
        if not isinstance(data, dict) or MemoryCompressor.KEY_PARTIAL not in data:
            return data

        try:
            raw = zlib.decompress(data[MemoryCompressor.KEY_PARTIAL])
            return raw.decode('utf-8')
        except Exception as e:
            print(f"⚠️ decompress_partial error: {e}")
            return None

    # ─────────────────────────────────────────────
    # دوال مساعدة
    # ─────────────────────────────────────────────

    @staticmethod
    def _compress_to_dict(data: Any, level: int = 6) -> dict:
        """ضغط البيانات وإرجاع dict موحد"""
        json_str   = json.dumps(data, separators=(',', ':'))
        compressed = zlib.compress(json_str.encode('utf-8'), level=level)
        return {
            MemoryCompressor.KEY_COMPRESSED:      compressed,
            MemoryCompressor.KEY_ORIGINAL_SIZE:   len(json_str),
            MemoryCompressor.KEY_COMPRESSED_SIZE: len(compressed),
            MemoryCompressor.KEY_RATIO:           len(compressed) / len(json_str)
                                                  if json_str else 0.0
        }

    @staticmethod
    def get_compression_stats(compressed_dict: dict) -> str:
        """ملخص إحصائيات الضغط"""
        if not compressed_dict:
            return "No data"
        orig  = compressed_dict.get(MemoryCompressor.KEY_ORIGINAL_SIZE, 0)
        comp  = compressed_dict.get(MemoryCompressor.KEY_COMPRESSED_SIZE, 0)
        ratio = compressed_dict.get(MemoryCompressor.KEY_RATIO, 0)
        return f"Original: {orig:,}B → Compressed: {comp:,}B ({ratio:.1%} ratio)"
