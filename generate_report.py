import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import csv

# 🏦 交易所字典 (用來辨識資金是來自交易所還是私人)
# 🏦 擴充版交易所字典 (加入了從數據中反向找出的隱藏熱錢包)
CEX_WALLETS = {
    # 原始已知
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pT42JA": "Binance",
    "2ojv9BAiHUrvsm9gxDe7fJSzbNZSJcxZvf8dqmWGHG8S": "Binance",
    "5tzFkiKscXHK5ZXCGbXZcmAz51GiyXyVka3YyN4Rz4rD": "OKX",
    "9WzDXwBbmcg8ZTZe1pTPp12338Qne2f51rZ7rU5KUMM4": "KuCoin",
    "Ac5rvv4RXZr9j8jGkXYWbE98kC9F9z2JtZJ8492iP8mY": "Bybit",
    "A77HErqtfN1hLLpvZhb8Qz2n5a7Qp44p83qXz25n61Uq": "Gate.io",
    # 🚨 新增：從本次跑出的數據中，揪出的跨幣種熱錢包 (高機率為 Binance/OKX)
    "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9": "CEX_HotWallet_A", # 出現於 PNUT, BOME, WIF
    "ASTyfSima4LLAdDgoFGkgqoKowG1LZFDr9fAQrg7iaJZ": "CEX_HotWallet_B", # 出現於 GOAT, PONKE
    "C68a6RCGLiPskbPYtAcsCjhG8tfTWYcoB4JjCrXFdqyo": "CEX_HotWallet_C", # 出現於 TRUMP
    "9AhKqLR67hwapvG8SA2JFXaCshXc9nALJjpKaHZrsbkw": "CEX_HotWallet_D", # 出現於 BONK
    "EPP7G9CaC9x8EVHnjqLP7F3wJKe1BYXXytF4CSQaFaj9": "CEX_HotWallet_E", # 出現於 MEW
}

def generate_csv():
    print(f"\n{'='*60}")
    print(f" 📊 讀書會報告：老鼠倉聚集度報表產生器 (獨立子資料夾版)")
    print(f"{'='*60}\n")

    # 📂 1. 定義輸入資料夾 (讀取 json)
    input_dir = os.path.join("2_data_processed", "batch_funder_engine")
    
    # 📂 2. 定義與自動建立你的新資料夾路徑
    # 會在 3_reports_txt 底下建立 first_funder_analysis 子資料夾
    report_dir = os.path.join("3_reports_txt", "first_funder_analysis")
    os.makedirs(report_dir, exist_ok=True) 
    
    # 將輸出 CSV 路徑指向新的子資料夾
    output_file = os.path.join(report_dir, "funder_report_summary.csv")

    if not os.path.exists(input_dir):
        print("❌ 找不到 JSON 資料夾，請確認 batch_funder_engine 已經跑完！")
        return

    report_data = []

    # 逐一讀取 20 個幣的 JSON 檔案
    for filename in os.listdir(input_dir):
        if not filename.endswith("_funder.json"):
            continue

        filepath = os.path.join(input_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        coin = data.get("coin", filename.replace("_funder.json", ""))
        clusters = data.get("funder_clusters", {})
        wallet_details = data.get("wallet_details", [])

        total_wallets = len(wallet_details)
        unique_funders = len(clusters)

        cex_funded_count = 0
        private_funded_count = 0
        unknown_count = 0
        max_private_cluster_size = 0
        max_private_funder = "無"

        # 分析這個幣的金主分佈
        for funder, count in clusters.items():
            if funder in ["Unknown", "Parse_Error"]:
                unknown_count += count
            elif funder in CEX_WALLETS:
                cex_funded_count += count
            else:
                private_funded_count += count
                # 揪出最大的私人莊家 (老鼠倉母體)
                if count > max_private_cluster_size:
                    max_private_cluster_size = count
                    max_private_funder = funder

        # 計算「資金聚集度」
        valid_wallets = total_wallets - unknown_count
        if valid_wallets > 0:
            clustering_ratio = round(((valid_wallets - unique_funders) / valid_wallets) * 100, 2)
        else:
            clustering_ratio = 0

        report_data.append({
            "代幣名稱 (Coin)": coin,
            "分析大戶數": total_wallets,
            "獨立資金源數": unique_funders,
            "資金聚集度 (%)": max(0, clustering_ratio), # 避免負數
            "CEX (交易所) 資金數": cex_funded_count,
            "私人錢包 資金數": private_funded_count,
            "最大單一私人莊家控制數": max_private_cluster_size,
            "最大莊家地址": max_private_funder,
            "解析失敗/未知數": unknown_count
        })

    if not report_data:
        print("⚠️ 沒有找到任何資料可以匯出。")
        return

    # 依照「資金聚集度」由高到低排序，最可疑的幣排在最前面
    report_data = sorted(report_data, key=lambda x: x["資金聚集度 (%)"], reverse=True)

    # 輸出成 CSV (加上 utf-8-sig 確保 Excel 打開中文不會亂碼)
    headers = report_data[0].keys()
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(report_data)

    print(f"✅ 報表輸出成功！")
    print(f"👉 檔案已存入獨立子資料夾：【 {report_dir} 】")
    print(f"👉 完整絕對路徑：D:\\生活\\1.參加競賽活動\\115\\2026鏈上數據讀書會\\meme_project\\my_project\\3_reports_txt\\first_funder_analysis\\funder_report_summary.csv\n")

if __name__ == "__main__":
    generate_csv()