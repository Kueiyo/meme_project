import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import pandas as pd

def generate_html_dashboards():
    # ── 1. 檔案讀取路徑 (CSV 與 JSON) ─────────────────────────────────────────
    # v2 的 CSV 計算結果 (提供: 錢包關聯度、CEX數量)
    report_file = os.path.join("3_reports_txt", "first_funder_analysis", "final_funder_report_v2.csv")

    # Step 2 的 JSON 存放資料夾 (提供: 前50大戶佔比、早鳥佔比)
    dir_metrics = "2_data_processed"

    # ── 2. 設定 HTML 的獨立輸出路徑 ─────────────────────────────────────────
    dir_html = os.path.join("5_reports_html", "funder_tracker_dashboards")
    os.makedirs(dir_html, exist_ok=True)

    # 防呆檢查：確認 CSV 是否存在
    if not os.path.exists(report_file):
        print(f"❌ 找不到 v2 報告檔，請確認路徑：\n{report_file}")
        return

    # ── 3. 開始讀取資料並批次生成 HTML 網頁 ─────────────────────────────────
    report_df = pd.read_csv(report_file)
    print("🌐 開始產出 v2 Tailwind + Chart.js 互動式網頁儀表板...")

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
                concentration = float(data.get("top50_concentration", 0.0))
                early_ratio = float(data.get("early_buyers_ratio", 0.0))
        else:
            print(f"   ⚠️ [{coin}] 找不到對應的 metrics.json，相關比例將以 0.0 計算。")

        # ── 4. 構建完整的 HTML 與 JavaScript 代碼 ───────────────────────────
        # 注意：使用 f-string 時，JavaScript 的花括號 {} 必須寫成雙花括號 {{}} 以免轉義報錯
        html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{coin} - 鏈上籌碼結構分析 (v2)</title>
    <!-- 引入 Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- 引入 Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-900 text-white font-sans p-8 min-h-screen">
    <div class="max-w-5xl mx-auto">
        
        <!-- 頂部頁籤標題區塊 -->
        <div class="flex items-center justify-between border-b border-gray-700 pb-4 mb-8 mt-4">
            <h1 class="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-emerald-400">
                🪙 {coin} <span class="text-2xl text-gray-400 font-normal">鏈上籌碼結構分析 (v2)</span>
            </h1>
            <span class="px-4 py-1.5 bg-gray-800 rounded-full text-sm font-medium border border-gray-600 shadow-md">
                2026 鏈上數據讀書會專案
            </span>
        </div>

        <!-- 四大核心數據卡片區塊 -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-6 mb-10">
            <!-- 集中度卡片 -->
            <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg hover:border-red-500 transition">
                <h3 class="text-gray-400 text-sm mb-2 font-semibold tracking-wide">Top 50 集中度</h3>
                <p class="text-3xl font-bold text-red-400">{concentration:.2%}</p>
            </div>
            
            <!-- 老鼠倉關聯度卡片 -->
            <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg hover:border-blue-500 transition relative overflow-hidden">
                <div class="absolute -right-4 -bottom-4 opacity-10 text-7xl select-none">🐀</div>
                <h3 class="text-gray-400 text-sm mb-2 font-semibold tracking-wide relative z-10">群聚係數 (老鼠倉風險)</h3>
                <p class="text-3xl font-bold text-blue-400 relative z-10">{clustering:.2%}</p>
            </div>
            
            <!-- 早鳥比例卡片 -->
            <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg hover:border-green-500 transition">
                <h3 class="text-gray-400 text-sm mb-2 font-semibold tracking-wide">早鳥比例</h3>
                <p class="text-3xl font-bold text-green-400">{early_ratio:.2%}</p>
            </div>
            
            <!-- CEX 錢包數卡片 -->
            <div class="bg-gradient-to-br from-orange-900 to-gray-800 p-6 rounded-xl border border-orange-500 shadow-lg relative overflow-hidden">
                <div class="absolute right-2 bottom-2 opacity-20 text-6xl select-none">🏦</div>
                <h3 class="text-orange-200 text-sm mb-2 font-semibold tracking-wide relative z-10">CEX (交易所) 錢包數</h3>
                <p class="text-4xl font-bold text-orange-400 relative z-10">{cex_count}</p>
            </div>
        </div>

        <!-- 互動式圖表容器區塊 -->
        <div class="bg-gray-800 p-8 rounded-xl border border-gray-700 shadow-xl">
            <h2 class="text-2xl font-semibold mb-6 text-gray-200 flex items-center gap-2">
                <span>📊</span> 籌碼健康度多維度評估
            </h2>
            <div class="relative h-72 w-full">
                <canvas id="metricsChart"></canvas>
            </div>
        </div>
        
    </div>

    <!-- Chart.js 核心繪圖邏輯 -->
    <script>
        const ctx = document.getElementById('metricsChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: ['早鳥比例 (Early Buyers)', '群聚係數 (Clustering)', 'Top 50 集中度 (Concentration)'],
                datasets: [{{
                    label: '指標分數 (0.0 ~ 1.0)',
                    data: [{early_ratio}, {clustering}, {concentration}],
                    backgroundColor: [
                        'rgba(74, 222, 128, 0.85)', // 綠色
                        'rgba(96, 165, 250, 0.85)', // 藍色
                        'rgba(248, 113, 113, 0.85)'  // 紅色
                    ],
                    borderColor: [
                        'rgb(34, 197, 94)',
                        'rgb(59, 130, 246)',
                        'rgb(239, 68, 68)'
                    ],
                    borderWidth: 2,
                    borderRadius: 6
                }}]
            }},
            options: {{
                indexAxis: 'y', // 設定為水平長條圖
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    x: {{
                        max: 1.0,
                        beginAtZero: true,
                        grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                        ticks: {{ color: '#9ca3af', font: {{ size: 14 }} }}
                    }},
                    y: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#e5e7eb', font: {{ size: 15, weight: 'bold' }} }}
                    }}
                }},
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: 'rgba(17, 24, 39, 0.95)',
                        titleFont: {{ size: 15, weight: 'bold' }},
                        bodyFont: {{ size: 15 }},
                        padding: 14,
                        borderColor: 'rgba(107, 114, 128, 0.5)',
                        borderWidth: 1,
                        callbacks: {{
                            label: function(context) {{
                                const pct = (context.raw * 100).toFixed(2);
                                return ' 百分比得分: ' + pct + '% (純數值: ' + context.raw.toFixed(4) + ')';
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        
        # 寫入 HTML 檔案
        html_filename = os.path.join(dir_html, f"dashboard_{coin}.html")
        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(html_content.strip())

        print(f"✅ [{coin}] HTML 網頁儀表板生成完畢！")

    print(f"\n🎉 完美！所有 v2 網頁儀表板已寫入：\n{dir_html}")

if __name__ == "__main__":
    generate_html_dashboards()