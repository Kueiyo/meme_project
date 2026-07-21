import os
from dotenv import load_dotenv

# 從專案根目錄的 .env 讀取環境變數（.env 不會被提交到版控）
load_dotenv()

API_KEY = os.environ.get("HELIUS_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "找不到 HELIUS_API_KEY！請在專案根目錄建立 .env 檔案（可參考 .env.example），"
        "並填入你的 Helius API Key。"
    )
