import json
import matplotlib.pyplot as plt
import os

def run(coin_name, dir_processed, dir_txt, dir_img):
    # ── 1. 讀取 Step 2 的數據結果 ─────────────────────────────────
    json_filename = f"{dir_processed}/metrics_{coin_name}.json"
    
    # 【防呆機制】：如果找不到 Step2 算好的檔案，直接回報錯誤
    if not os.path.exists(json_filename):
        raise FileNotFoundError(f"找不到處理過的資料檔 {json_filename}，請確認 Step 2 是否執行成功。")

    with open(json_filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 抓取四個指標
    concentration = data.get("top50_concentration", 0)
    clustering = data.get("clustering_coefficient", 0)
    early_ratio = data.get("early_buyers_ratio", 0)
    cex_count = data.get("cex_wallet_count", 0)

    # ── 2. 生成並儲存 .txt 報告 (存入 dir_txt) ────────────────────
    report_text = f"""
╔══════════════════════════════════════════╗
║  {coin_name} 鏈上籌碼結構分析報告
╠══════════════════════════════════════════╣
║  籌碼集中度 (Top 50 Concentration)  : {concentration:.4f}
║  群聚係數 (Clustering Coefficient)  : {clustering:.4f}
║  早鳥比例 (Early Buyers Ratio)      : {early_ratio:.4f}
║  交易所錢包數 (CEX Wallet Count)    : {cex_count}
╚══════════════════════════════════════════╝
"""

    txt_filename = f"{dir_txt}/report_{coin_name}.txt"
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write(report_text.strip())
    print(f"✅ 文字報告已儲存：{txt_filename}")

    # ── 3. 繪製圖像化數據儀表板 Dashboard (存入 dir_img) ──────────
    # 設定為深色專業風格
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))

    # 定義長條圖的項目與數值 (只放 0~1 的小數指標)
    metrics = ['Early Buyers Ratio', 'Clustering Coefficient', 'Top 50 Concentration']
    values = [early_ratio, clustering, concentration]
    # 配色：淺綠、淺藍、珊瑚紅
    colors = ['#99FF99', '#66B2FF', '#FF9999'] 

    # 繪製水平長條圖
    bars = ax.barh(metrics, values, color=colors, alpha=0.85, edgecolor='white')

    # 設定 X 軸的範圍固定為 0 到 1，方便比較
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("Independent Metric Score (0.0 = Min, 1.0 = Max)", fontsize=12, color='lightgray')
    ax.set_title(f"{coin_name} On-Chain Metrics Dashboard", fontsize=18, fontweight='bold', pad=20)

    # 隱藏圖表的上下右邊框，讓畫面更乾淨
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')

    # 在每個長條圖右側標示具體數值
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.02, bar.get_y() + bar.get_height()/2, 
                f'{width:.4f}', 
                va='center', fontsize=12, color='white', fontweight='bold')

    # 處理 CEX 錢包數量：以醒目的資訊卡片顯示在右下角
    bbox_props = dict(boxstyle="round,pad=0.8", fc="#FFB366", ec="none", alpha=0.9)
    ax.text(0.95, 0.15, f"CEX Wallets Found:\n{cex_count}", 
            transform=ax.transAxes, fontsize=14, color='black', 
            fontweight='bold', ha='center', va='center', bbox=bbox_props)

    # 儲存圖片
    img_filename = f"{dir_img}/dashboard_{coin_name}.png"
    plt.tight_layout()
    plt.savefig(img_filename, dpi=300)
    plt.close()

    print(f"✅ 圖像化儀表板已儲存：{img_filename}")