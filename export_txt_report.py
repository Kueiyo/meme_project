import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import os
import json

def load_master_labels(master_csv="master_sheet.csv"):
    """讀取 master_sheet.csv 人工標註的『類型』欄（col 3），依代幣符號（col 2）比對"""
    labels = {}
    if not os.path.exists(master_csv):
        return labels

    df = pd.read_csv(master_csv, header=None)
    for r in range(2, len(df)):
        sym = df.iloc[r, 2]
        label = df.iloc[r, 3]
        if isinstance(sym, str) and sym.strip() and pd.notna(label):
            labels[sym.strip()] = str(label).strip()
    return labels

def export_to_txt():
    # ── 1. 檔案讀取與輸出路徑 ─────────────────────────────────────────
    # v2 的計算結果 (提供: 資金聚集度、CEX數量)
    report_file = os.path.join("3_reports_txt", "first_funder_analysis", "final_funder_report_v2.csv")

    # Step 2 的 JSON 存放資料夾 (提供: 前50大戶佔比、群聚係數/錢包關聯度、早鳥佔比)
    dir_metrics = "2_data_processed"

    # TXT 輸出路徑
    output_dir = os.path.join("3_reports_txt", "funder_tracker_dashboards")
    os.makedirs(output_dir, exist_ok=True)
    output_txt = os.path.join(output_dir, "讀書會報告_核心指標.txt")

    # 防呆：確認 CSV 是否存在
    if not os.path.exists(report_file):
        print(f"❌ 找不到 v2 報告檔，請確認路徑：\n{report_file}")
        return

    # master_sheet.csv 人工標註的「類型」是唯一的 ground truth，不能用被檢驗的指標反推
    master_labels = load_master_labels()

    # ── 2. 讀取 v2 報告並作為主迴圈 ───────────────────────────────────────
    report_df = pd.read_csv(report_file)
    results = []

    print("開始整合 CSV 與 JSON 數據...")

    for _, row in report_df.iterrows():
        coin = str(row['代幣名稱 (Coin)']).strip()

        # 從 CSV 抓取 Pipeline B 計算好的數據（僅 CEX 資金數，資金聚集度不等於錢包關聯度）
        cex = int(row['CEX (交易所) 資金數'])

        # 「類型」是人工標註的 ground truth，直接讀 master_sheet.csv，不能用被檢驗的指標反推
        label = master_labels.get(coin, "缺失標註")

        # ── 3. 從 JSON 抓取 Step 2 指標 ────────────────────────────────
        json_path = os.path.join(dir_metrics, f"metrics_{coin}.json")
        top50 = "缺失 JSON"
        clustering = "缺失 JSON"
        early = "缺失 JSON"

        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 抓取數值並四捨五入到小數點後四位
                top50_val = data.get("top50_concentration", 0)
                clustering_val = data.get("clustering_coefficient", 0)
                early_val = data.get("early_buyers_ratio", 0)
                top50 = round(float(top50_val), 4)
                clustering = round(float(clustering_val), 4)
                early = round(float(early_val), 4)
        else:
            print(f"  ⚠️ 找不到 [{coin}] 的 metrics JSON 檔案，相關欄位將標示為缺失。")

        # 將合併好的資料存入陣列
        results.append({
            'Symbol': coin,
            '類型': label,
            '前50大戶佔比': top50,
            '錢包關聯度': clustering,
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