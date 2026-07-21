import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import pandas as pd
import matplotlib.pyplot as plt

def generate_dashboards():
    # ── 1. 檔案讀取路徑 (CSV 與 JSON) ─────────────────────────────────────────
    # v2 的 CSV 計算結果 (提供: 錢包關聯度、CEX數量)
    report_file = os.path.join("3_reports_txt", "first_funder_analysis", "final_funder_report_v2.csv")

    # Step 2 的 JSON 存放資料夾 (提供: 前50大戶佔比、早鳥佔比)
    dir_metrics = "2_data_processed"

    # ── 2. 設定 TXT 與 IMG 的獨立輸出路徑 ───────────────────────────────────
    dir_txt = os.path.join("3_reports_txt", "funder_tracker_dashboards")
    dir_img = os.path.join("4_reports_img", "funder_tracker_dashboards")
    
    # 自動建立輸出資料夾
    os.makedirs(dir_txt, exist_ok=True)
    os.makedirs(dir_img, exist_ok=True)

    # 防呆檢查：確認 CSV 是否存在
    if not os.path.exists(report_file):
        print(f"❌ 找不到 v2 報告檔，請確認路徑：\n{report_file}")
        return

    # ── 3. 開始讀取資料並批次生成圖表 ───────────────────────────────────────
    report_df = pd.read_csv(report_file)
    print("🎨 開始繪製 v2 數據儀表板 (包含純文字報告與 PNG 圖表)...")

    for _, row in report_df.iterrows():
        # 從 CSV 提取代幣名稱與 v2 指標
        coin = str(row['代幣名稱 (Coin)']).strip()
        clustering = float(row['資金聚集度 (%)']) / 100  # 轉成 0~1 的小數
        cex_count = int(row['CEX (交易所) 資金數'])

        # 從 JSON 提取對應的原始指標
        concentration = 0.0
        early_ratio = 0.0
        json_path = os.path.join(dir_metrics, f"metrics_{coin}.json")
        
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 使用 float 確保數值格式正確，避免 KeyError 造成程式中斷
                concentration = float(data.get("top50_concentration", 0.0))
                early_ratio = float(data.get("early_buyers_ratio", 0.0))
        else:
            print(f"   ⚠️ [{coin}] 找不到對應的 metrics.json，相關比例將以 0.0 計算。")

        # ── 4. 生成並儲存 .txt 報告[cite: 1] ──────────────────────────────────
        report_text = f"""
╔══════════════════════════════════════════╗
║  {coin} 鏈上籌碼結構分析報告 (v2 升級版)
╠══════════════════════════════════════════╣
║  籌碼集中度 (Top 50 Concentration)  : {concentration:.4f}
║  群聚係數 (Clustering Coefficient)  : {clustering:.4f}
║  早鳥比例 (Early Buyers Ratio)      : {early_ratio:.4f}
║  交易所錢包數 (CEX Wallet Count)    : {cex_count}
╚══════════════════════════════════════════╝
"""
        txt_filename = os.path.join(dir_txt, f"report_{coin}.txt")
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write(report_text.strip())

        # ── 5. 繪製圖像化數據儀表板 Dashboard[cite: 1] ───────────────────────
        # 設定為深色專業風格[cite: 1]
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 6))

        # 定義長條圖的項目與數值 (只放 0~1 的小數指標)[cite: 1]
        metrics = ['Early Buyers Ratio', 'Clustering Coefficient', 'Top 50 Concentration']
        values = [early_ratio, clustering, concentration]
        
        # 配色：淺綠、淺藍、珊瑚紅[cite: 1]
        colors = ['#99FF99', '#66B2FF', '#FF9999'] 

        # 繪製水平長條圖[cite: 1]
        bars = ax.barh(metrics, values, color=colors, alpha=0.85, edgecolor='white')

        # 設定 X 軸的範圍固定為 0 到 1，方便比較[cite: 1]
        ax.set_xlim(0, 1.1)
        ax.set_xlabel("Independent Metric Score (0.0 = Min, 1.0 = Max)", fontsize=12, color='lightgray')
        ax.set_title(f"{coin} On-Chain Metrics Dashboard (v2)", fontsize=18, fontweight='bold', pad=20)

        # 隱藏圖表的上下右邊框，讓畫面更乾淨[cite: 1]
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('gray')
        ax.spines['left'].set_color('gray')

        # 在每個長條圖右側標示具體數值[cite: 1]
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 0.02, bar.get_y() + bar.get_height()/2, 
                    f'{width:.4f}', 
                    va='center', fontsize=12, color='white', fontweight='bold')

        # 處理 CEX 錢包數量：以醒目的資訊卡片顯示在右下角[cite: 1]
        bbox_props = dict(boxstyle="round,pad=0.8", fc="#FFB366", ec="none", alpha=0.9)
        ax.text(0.95, 0.15, f"CEX Wallets Found:\n{cex_count}", 
                transform=ax.transAxes, fontsize=14, color='black', 
                fontweight='bold', ha='center', va='center', bbox=bbox_props)

        # 儲存圖片[cite: 1]
        img_filename = os.path.join(dir_img, f"dashboard_{coin}.png")
        plt.tight_layout()
        plt.savefig(img_filename, dpi=300)
        plt.close()

        print(f"✅ [{coin}] 報告與圖表生成完畢！")

    print(f"\n🎉 大功告成！檔案已分類存放：")
    print(f" 📄 文字報告: {dir_txt}")
    print(f" 🖼️ 視覺圖表: {dir_img}")

if __name__ == "__main__":
    generate_dashboards()