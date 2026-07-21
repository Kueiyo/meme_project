import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import pandas as pd

# 讀取 v2 引擎產出的最新乾淨資料
INPUT_DIR = os.path.join("2_data_processed", "batch_funder_engine_v2")

# 輸出至獨立子資料夾，與 export_txt_report.py / generate_v2_dashboards.py 等下游腳本的讀取路徑一致
REPORT_DIR = os.path.join("3_reports_txt", "first_funder_analysis")
OUTPUT_FILE = os.path.join(REPORT_DIR, "final_funder_report_v2.csv")

# 🏦 擴充版交易所字典 (涵蓋了我們前面揪出的跨幣種熱錢包)
CEX_WALLETS = {
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pT42JA": "Binance",
    "2ojv9BAiHUrvsm9gxDe7fJSzbNZSJcxZvf8dqmWGHG8S": "Binance",
    "5tzFkiKscXHK5ZXCGbXZcmAz51GiyXyVka3YyN4Rz4rD": "OKX",
    "9WzDXwBbmcg8ZTZe1pTPp12338Qne2f51rZ7rU5KUMM4": "KuCoin",
    "Ac5rvv4RXZr9j8jGkXYWbE98kC9F9z2JtZJ8492iP8mY": "Bybit",
    "A77HErqtfN1hLLpvZhb8Qz2n5a7Qp44p83qXz25n61Uq": "Gate.io",
    # 隱藏版熱錢包/造市商
    "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9": "CEX_HotWallet_A", 
    "ASTyfSima4LLAdDgoFGkgqoKowG1LZFDr9fAQrg7iaJZ": "CEX_HotWallet_B", 
    "C68a6RCGLiPskbPYtAcsCjhG8tfTWYcoB4JjCrXFdqyo": "CEX_HotWallet_C", 
    "9AhKqLR67hwapvG8SA2JFXaCshXc9nALJjpKaHZrsbkw": "CEX_HotWallet_D", 
    "EPP7G9CaC9x8EVHnjqLP7F3wJKe1BYXXytF4CSQaFaj9": "CEX_HotWallet_E",
    "4xLpwxgYuPwPvtQjE94RLS4WZ4aD8NJYYKr2AJk99Qdg": "CEX_HotWallet_F", # 先前在多個大幣中重複出現的造市商/熱錢包
    "AC5RDfQFmDS1deWZos921JfqscXdByf8BKHs5ACWjtW2": "CEX_HotWallet_G"
}

def generate_report():
    if not os.path.exists(INPUT_DIR):
        print(f"❌ 找不到資料夾: {INPUT_DIR}")
        return

    os.makedirs(REPORT_DIR, exist_ok=True)

    report_data = []

    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith("_funder.json"):
            continue
            
        filepath = os.path.join(INPUT_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        coin_name = data.get("coin", filename.split("_")[0])
        funder_clusters = data.get("funder_clusters", {})
        
        # 統計基礎指標
        total_wallets = sum(funder_clusters.values())
        unique_funders = len(funder_clusters)
        
        cex_count = 0
        private_count = 0
        unknown_count = 0
        
        private_funders = {}

        # 重新分類 (確保套用最新的擴充字典)
        for funder, count in funder_clusters.items():
            if funder in ["Unknown", "Parse_Error"]:
                unknown_count += count
            elif funder in CEX_WALLETS:
                cex_count += count
            else:
                private_count += count
                private_funders[funder] = count
                
        # 尋找最大私人莊家 (過濾掉交易所後，控制最多大戶的單一私人錢包)
        max_private_control = 0
        max_private_address = "None"
        if private_funders:
            max_private_address = max(private_funders, key=private_funders.get)
            max_private_control = private_funders[max_private_address]

        # 資金聚集度算法：最大私人莊家控制數 / 總大戶數
        concentration_pct = round((max_private_control / total_wallets) * 100, 2) if total_wallets > 0 else 0

        report_data.append({
            "代幣名稱 (Coin)": coin_name,
            "分析大戶數": total_wallets,
            "獨立資金源數": unique_funders,
            "資金聚集度 (%)": concentration_pct,
            "CEX (交易所) 資金數": cex_count,
            "私人錢包 資金數": private_count,
            "最大單一私人莊家控制數": max_private_control,
            "最大莊家地址": max_private_address,
            "解析失敗/未知數": unknown_count
        })

    # 轉換成 DataFrame 並依據資金聚集度排序
    df = pd.DataFrame(report_data)
    if not df.empty:
        df = df.sort_values(by="資金聚集度 (%)", ascending=False)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"✅ 完美報表已成功產出！儲存於: {OUTPUT_FILE}")
        print(df.to_string(index=False))
    else:
        print("⚠️ 沒有可用的資料來產生報表。")

if __name__ == "__main__":
    generate_report()