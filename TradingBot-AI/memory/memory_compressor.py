# memory_compressor.py - في الذاكرة فقط
import zlib
import json

class MemoryCompressor:
    """يضغط البيانات الكبيرة ويخزنها في الذاكرة فقط"""
    
    @staticmethod
    def compress_candles(candles_data):
        """يضغط شموع التحليل في الذاكرة فقط"""
        if not candles_data:
            return None
        
        # نحذف البيانات المكررة والغير مهمة
        cleaned_data = []
        for candle in candles_data:
            if len(candle) >= 6:  # [timestamp, open, high, low, close, volume]
                cleaned_candle = [
                    int(candle[0]),      # timestamp
                    float(candle[1]),    # open
                    float(candle[2]),    # high
                    float(candle[3]),    # low
                    float(candle[4]),    # close
                    float(candle[5])     # volume
                ]
                cleaned_data.append(cleaned_candle)
        
        # نحول البيانات لنص مضغوط
        json_str = json.dumps(cleaned_data, separators=(',', ':'))  # إزالة المسافات
        compressed = zlib.compress(json_str.encode('utf-8'), level=9)  # أعلى ضغط
        
        return {
            'compressed': compressed,
            'original_size': len(json_str),
            'compressed_size': len(compressed),
            'ratio': len(compressed) / len(json_str)
        }
    
    @staticmethod
    def decompress_candles(compressed_data):
        """يفك ضغط الشموع من الذاكرة فقط"""
        if not compressed_data or 'compressed' not in compressed_data:
            return None
        
        try:
            decompressed = zlib.decompress(compressed_data['compressed'])
            return json.loads(decompressed.decode('utf-8'))
        except Exception as e:
            print(f"⚠️ فشل فك الضغط: {e}")
            return None
    
    @staticmethod
    def compress_analysis_result(analysis_data):
        """يضغط نتائج التحليل في الذاكرة فقط"""
        if not analysis_data:
            return None
        
        # نأخذ البيانات المهمة فقط
        essential_data = {
            'signal': analysis_data.get('signal'),
            'confidence': analysis_data.get('confidence'),
            'rsi': analysis_data.get('indicators', {}).get('rsi'),
            'macd': analysis_data.get('indicators', {}).get('macd'),
            'price': analysis_data.get('price')
        }
        
        json_str = json.dumps(essential_data)
        compressed = zlib.compress(json_str.encode('utf-8'))
        
        return {
            'compressed': compressed,
            'original_size': len(json_str),
            'compressed_size': len(compressed)
        }