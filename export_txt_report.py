import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import os
import json

def export_to_txt():
    # ── 1. 檔案讀取與輸出路徑 ─────────────────────────────────────────
    # v2 的計算結果 (提供: 錢包關聯度、CEX數量)
    report_file = os.path.join("3_reports_txt", "first_funder_analysis", "final_funder_report_v2.csv")

    # Step 2 的 JSON 存放資料夾 (提供: 前50大戶佔比、早鳥佔比)
    dir_metrics = "2_data_processed"

    # TXT 輸出路徑
    output_dir = os.path.join("3_reports_txt", "funder_tracker_dashboards")
    os.makedirs(output_dir, exist_ok=True)
    output_txt = os.path.join(output_dir, "讀書會報告_核心指標.txt")

    # 防呆：確認 CSV 是否存在
    if not os.path.exists(report_file):
        print(f"❌ 找不到 v2 報告檔，請確認路徑：\n{report_file}")
        return

    # ── 2. 讀取 v2 報告並作為主迴圈 ───────────────────────────────────────
    report_df = pd.read_csv(report_file)
    results = []

    print("開始整合 CSV 與 JSON 數據...")

    for _, row in report_df.iterrows():
        coin = str(row['代幣名稱 (Coin)']).strip()
        
        # 從 CSV 抓取計算好的數據
        clust = float(row['資金聚集度 (%)']) / 100
        cex = int(row['CEX (交易所) 資金數'])
        
        # 自動判定操盤風險 (設定閾值為 15%，超過則判定為 1)
        label = "1" if clust >= 0.15 else "0"

        # ── 3. 從 JSON 抓取 Step 2 指標 ────────────────────────────────
        json_path = os.path.join(dir_metrics, f"metrics_{coin}.json")
        top50 = "缺失 JSON"
        early = "缺失 JSON"
        
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 抓取數值並四捨五入到小數點後四位
                top50_val = data.get("top50_concentration", 0)
                early_val = data.get("early_buyers_ratio", 0)
                top50 = round(float(top50_val), 4)
                early = round(float(early_val), 4)
        else:
            print(f"  ⚠️ 找不到 [{coin}] 的 metrics JSON 檔案，相關欄位將標示為缺失。")

        # 將合併好的資料存入陣列
        results.append({
            'Symbol': coin,
            '類型': label,
            '前50大戶佔比': top50,
            '錢包關聯度': round(clust, 4),
            '早鳥佔比': early,
            'CEX地址數': cex
        })

    # ── 4. 寫入 TXT 檔案 ─────────────────────────────────────────
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write("============================================================\n")
        f.write(" 📊 讀書會專案：Meme Coin 核心指標報告 (純程式自動串接版)\n")
        f.write("============================================================\n\n")
        
        for res in results:
            f.write(f"🪙 代幣名稱: {res['Symbol']}\n")
            f.write(f"   - 類型 (1=操盤/0=正常) : {res['類型']}\n")
            f.write(f"   - 前50大戶佔比 (A2)    : {res['前50大戶佔比']}\n")
            f.write(f"   - 錢包關聯度 (A2)      : {res['錢包關聯度']}\n")
            f.write(f"   - 早鳥佔比 (A2)        : {res['早鳥佔比']}\n")
            f.write(f"   - CEX地址數 (A2)       : {res['CEX地址數']}\n")
            f.write("-" * 60 + "\n")

    print(f"\n✅ 完美！已成功整合所有數據並生成：\n{output_txt}")

if __name__ == "__main__":
    export_to_txt()