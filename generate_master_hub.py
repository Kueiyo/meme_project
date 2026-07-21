import os
import glob

def generate_master_dashboard():
    # ── 1. 資料夾路徑設定 ─────────────────────────────────────────
    spider_dir = r"D:\生活\1.參加競賽活動\115\2026鏈上數據讀書會\meme_project\my_project\5_reports_html\v2_spider_graphs"
    output_dir = r"D:\生活\1.參加競賽活動\115\2026鏈上數據讀書會\meme_project\my_project\5_reports_html"
    output_html = os.path.join(output_dir, "master_dashboard.html")

    if not os.path.exists(spider_dir):
        print(f"❌ 找不到蜘蛛網圖資料夾：\n{spider_dir}")
        return

    # ── 2. 自動搜尋所有 spider_*.html 檔案 ────────────────────────
    pattern = os.path.join(spider_dir, "spider_*.html")
    html_files = glob.glob(pattern)

    if not html_files:
        print(f"❌ 在 {spider_dir} 中找不到任何 spider_*.html 檔案。請先執行蜘蛛網產生腳本。")
        return

    coins = []
    for file_path in html_files:
        filename = os.path.basename(file_path)
        # 從 spider_HAWK.html 萃取出代幣名稱 HAWK
        coin_name = filename.replace("spider_", "").replace(".html", "")
        # 計算相對於主控台 HTML 的相對路徑 (供 iframe 使用)
        rel_path = os.path.relpath(file_path, output_dir).replace("\\", "/")
        coins.append({"name": coin_name, "path": rel_path})

    # 依代幣名稱字母排序
    coins = sorted(coins, key=lambda x: x["name"])
    coins_json = str(coins).replace("'", '"')

    # ── 3. 組合前端整合介面 (Tailwind CSS 側邊欄 + iframe) ────────
    master_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meme 鏈上大戶資金溯源 - 綜合控制台</title>
    <!-- 引入 Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-950 text-white font-sans h-screen flex overflow-hidden">

    <!-- 左側導覽列 (Sidebar) -->
    <aside class="w-72 bg-gray-900 border-r border-gray-800 flex flex-col h-full shadow-2xl">
        <!-- 標題區 -->
        <div class="p-6 border-b border-gray-800">
            <h1 class="text-xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-emerald-400">
                🪙 Meme 資金溯源中樞
            </h1>
            <p class="text-xs text-gray-400 mt-1">2026 鏈上數據讀書會專案</p>
        </div>

        <!-- 代幣清單按鈕區 (支援捲動) -->
        <div id="coin-list" class="flex-1 overflow-y-auto p-4 space-y-2">
            <!-- 動態注入項目 -->
        </div>
        
        <!-- 底部提示 -->
        <div class="p-4 border-t border-gray-800 text-xs text-center text-gray-500">
            點擊清單即時切換互動拓撲圖
        </div>
    </aside>

    <!-- 右側主要內容顯示區 (Main Content) -->
    <main class="flex-1 flex flex-col h-full bg-gray-950 relative">
        <!-- 頂部資訊列 -->
        <header class="h-16 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-8 shadow-md">
            <div class="flex items-center space-x-3">
                <span class="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></span>
                <h2 id="current-title" class="text-lg font-bold text-gray-200">請從左側選擇代幣</h2>
            </div>
            <div class="text-sm text-gray-400 bg-gray-800 px-3 py-1 rounded-full border border-gray-700">
                互動式蜘蛛網拓撲引擎 (v2)
            </div>
        </header>

        <!-- 嵌入 iframe 顯示對應的蜘蛛網圖 -->
        <div class="flex-1 w-full h-full relative bg-gray-950">
            <iframe id="report-frame" src="" class="w-full h-full border-0"></iframe>
        </div>
    </main>

    <!-- 前端互動切換邏輯 -->
    <script>
        const coinsData = {coins_json};

        const coinListContainer = document.getElementById('coin-list');
        const iframe = document.getElementById('report-frame');
        const currentTitle = document.getElementById('current-title');

        function loadCoin(coinName, relativePath) {{
            // 更新 iframe 來源網址
            iframe.src = relativePath;
            currentTitle.innerText = `目前檢視代幣: ${{coinName}}`;

            // 更新左側按鈕的選取樣式
            document.querySelectorAll('.coin-btn').forEach(btn => {{
                btn.classList.remove('bg-cyan-600', 'text-white', 'shadow-lg');
                btn.classList.add('bg-gray-800', 'text-gray-300', 'hover:bg-gray-700');
            }});
            
            const activeBtn = document.getElementById(`btn-${{coinName}}`);
            if (activeBtn) {{
                activeBtn.classList.remove('bg-gray-800', 'text-gray-300', 'hover:bg-gray-700');
                activeBtn.classList.add('bg-cyan-600', 'text-white', 'shadow-lg');
            }}
        }}

        // 初始化建立左側按鈕清單
        coinsData.forEach((item, index) => {{
            const btn = document.createElement('button');
            btn.id = `btn-${{item.name}}`;
            btn.className = 'coin-btn w-full text-left px-4 py-3 rounded-xl font-medium transition duration-200 flex items-center justify-between bg-gray-800 text-gray-300 hover:bg-gray-700 text-sm';
            btn.innerHTML = `<span>🪙 ${{item.name}}</span> <span class="text-xs text-gray-500">▶</span>`;
            btn.onclick = () => loadCoin(item.name, item.path);
            coinListContainer.appendChild(btn);

            // 預設自動載入第一個代幣
            if (index === 0) {{
                loadCoin(item.name, item.path);
            }}
        }});
    </script>
</body>
</html>
"""

    os.makedirs(output_dir, exist_ok=True)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(master_html)

    print(f"✅ 完美！已成功產生綜合導覽控制台：\n{output_html}")

if __name__ == "__main__":
    generate_master_dashboard()