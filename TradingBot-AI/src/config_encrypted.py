import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# تحميل متغيرات البيئة من ملف .env
try:
    from dotenv import load_dotenv
    import pathlib
    # البحث عن .env في عدة مسارات
    for env_path in [
        pathlib.Path('/home/container/TradingBot/.env'),
        pathlib.Path('/home/container/.env'),
        pathlib.Path(__file__).parent / '.env',
        pathlib.Path(__file__).parent.parent / '.env',
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            break
except:
    pass

# المفاتيح المشفرة (آمنة!)
ENCRYPTED_API_KEY = "gAAAAABpqNT5S7vbJXLley0iN7H-kBtbmUZofnkpdadW0a3ygU6JyPxGCpCDUCzeXq9Vwv85JM4Tf9X-1Oe-oJrTFCpZ0gfthS_T6whxOtj8K60gCnG-hd8GRi0rsunWJEq1D2dZsJc6QEXGwrxhD9NOWeiHHYxY3GthbjH7alHNhu_7VY7BXiU="
ENCRYPTED_SECRET_KEY = "gAAAAABpqNT51kkfLH9UbjItW_Gp-g93Fs6QT5h4g_rOhIK4n3cs3_K7ZMDBEEw_yrh-JJbbVSJS3-PzH9cZ7ta86_T_Em9N3Yra8QbSiIojOW3yzGBA5lL3mgISOYj6bpbpW6Dt4zLunlpz62lsXGyba_SmsvdFTnf2YzNy2BQfzc__jULwvPM="
ENCRYPTED_WEBHOOK = "gAAAAABprab4hsuU0oVeIcTPlFqvimOULJLFRNAqFvSOwZtfwEJ6tEk9M4wvNjgcLlgZCysETBszSvYekkW4Zsba6qhpuLmR6wS4gT63WCRdwgJbw83OxIYU9tDEFN3RbUi2QSHR0sFQv8lkKCmEkl6pkCDnz8dAFcf91VBHQoRQNuUi5BaWl4WWuPi7Rz9X_FUsFTJ3b1y7g_n3RMiMuh3bErcLcejuQMmNXt4OsA3KEP3w6ZWhswU="
ENCRYPTED_CRITICAL_WEBHOOK = "gAAAAABpuay0FYK_AXFBy_trEWffy5Ho8xzGr4-zSrASVWnVqipfKR3_k6C9VsucFp1qPEzcHaXDb8txhiVUkFrXFKTD9XIguwTnCZcpj6FqnGTKi7-jaCDb3eHEdeNiZcmKpax4ma_WNrlRHLJDTVDSuWvtff41bmMLyohJ3_ezK3Ox0-8iHeVDnutL1oyU7sMHwWfWY4f12xvc--03MTYqu42u_0IfNbEvyCt2LGvDNlVIJcCkQeg="

# Master key for password encryption (hardcoded - secure)
_MASTER_KEY = base64.urlsafe_b64encode(b'MSA_TRADING_BOT_2026_SECRET_KEY!')
_MASTER_CIPHER = Fernet(_MASTER_KEY)

def get_encryption_key():
    """Get encryption key - supports Fernet encrypted password"""
    # Try Environment Variable first
    encrypted_key = os.getenv('ENCRYPTION_KEY')
    if not encrypted_key:
        for env_file in [
            '/home/container/TradingBot-AI/.env',
            '/home/container/TradingBot/.env',
            '/home/container/.env'
        ]:
            try:
                with open(env_file) as f:
                    for line in f:
                        if line.startswith('ENCRYPTION_KEY='):
                            encrypted_key = line.strip().split('=', 1)[1]
                            break
                if encrypted_key:
                    break
            except:
                pass
    
    if encrypted_key:
        try:
            # Try to decrypt with Fernet (strong encryption)
            decrypted = _MASTER_CIPHER.decrypt(encrypted_key.encode()).decode()
            print("✅ Encryption key loaded from environment variable (Fernet decrypted)")
            return decrypted
        except:
            # Fallback: try base64 (old method)
            try:
                decoded = base64.b64decode(encrypted_key).decode()
                print("✅ Encryption key loaded from environment variable (base64 decoded)")
                return decoded
            except:
                # Use as-is (plain text)
                print("✅ Encryption key loaded from environment variable")
                return encrypted_key
    
    # Try flash drive
    key_file = r"D:\bot_keys.txt"
    try:
        if os.path.exists(key_file):
            with open(key_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                key = lines[2].strip()  # السطر الثالث (المفتاح)
            print("✅ Encryption key loaded from flash drive")
            return key
        else:
            print("\n" + "="*60)
            print("⚠️  Flash drive not found!")
            print("📌 Please connect D:\\ drive with bot_keys.txt")
            print("📌 Or set ENCRYPTION_KEY environment variable")
            print("="*60 + "\n")
            return None
    except Exception as e:
        print("\n" + "="*60)
        print("⚠️  Error reading encryption key!")
        print("📌 Make sure bot_keys.txt exists in D:\\")
        print("📌 Or set ENCRYPTION_KEY environment variable")
        print("="*60 + "\n")
        return None

_KEY = get_encryption_key()

if not _KEY:
    exit()

def get_api_keys():
    """فك تشفير المفاتيح بكلمة السر الثابتة"""
    try:
        # توليد مفتاح التشفير من كلمة السر
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'binance_bot_salt_2026',
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(_KEY.encode()))
        fernet = Fernet(key)
        
        # فك التشفير
        api_key = fernet.decrypt(ENCRYPTED_API_KEY.encode()).decode()
        secret_key = fernet.decrypt(ENCRYPTED_SECRET_KEY.encode()).decode()
        
        return api_key, secret_key
    except:
        print("❌ Failed to decrypt keys!")
        return None, None

def get_discord_webhook():
    """فك تشفير Discord Webhook"""
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'binance_bot_salt_2026',
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(_KEY.encode()))
        fernet = Fernet(key)
        webhook = fernet.decrypt(ENCRYPTED_WEBHOOK.encode()).decode()
        return webhook
    except:
        return None

def get_critical_webhook():
    """فك تشفير Critical Alerts Webhook"""
    # If you provide a plain webhook via environment variable,
    # use it directly (avoids issues with a stale encrypted value).
    try:
        plain = os.getenv("CRITICAL_WEBHOOK_PLAIN")
        print(f"🧩 [CRITICAL WEBHOOK] CRITICAL_WEBHOOK_PLAIN present={bool(plain)} len={len(plain) if plain else 0}")
        if plain:
            return plain
    except:
        pass

    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'binance_bot_salt_2026',
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(_KEY.encode()))
        fernet = Fernet(key)
        print(f"🧩 [CRITICAL WEBHOOK] Decrypting ENCRYPTED_CRITICAL_WEBHOOK len={len(ENCRYPTED_CRITICAL_WEBHOOK)}")
        webhook = fernet.decrypt(ENCRYPTED_CRITICAL_WEBHOOK.encode()).decode()
        print("✅ [CRITICAL WEBHOOK] decrypt success")
        return webhook
    except Exception as e:
        print(f"❌ [CRITICAL WEBHOOK] decrypt failed: {type(e).__name__}: {e}")
        return None
