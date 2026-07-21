import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import networkx as nx
from pyvis.network import Network

def generate_spider_web_graphs():
    # ── 1. 檔案讀取與獨立輸出路徑 ─────────────────────────────────────────
    # 讀取 v2 引擎算好的 First Funder 乾淨數據 (JSON)
    input_dir = os.path.join("2_data_processed", "batch_funder_engine_v2")

    # 獨立存放在 5_reports_html 底下的專屬資料夾 v2_spider_graphs
    output_dir = os.path.join("5_reports_html", "v2_spider_graphs")
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_dir):
        print(f"❌ 找不到 v2 JSON 資料夾：\n{input_dir}")
        return

    # ── 2. 開始批次處理每個幣種的 JSON ─────────────────────────────────────
    print("🕸️ 開始繪製 v2 第一桶金蜘蛛網關聯圖 (PyVis 互動式 HTML)...")

    for filename in os.listdir(input_dir):
        if not filename.endswith("_funder.json"):
            continue
            
        filepath = os.path.join(input_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        coin_name = data.get("coin", filename.split("_")[0])
        funder_clusters = data.get("funder_clusters", {})

        # ── 3. 建立關聯網路 (NetworkX) ──────────────────────────────────
        G_for_plot = nx.Graph()
        
        wallet_counter = 1
        for funder_addr, count in funder_clusters.items():
            # 過濾掉解析失敗的過濾筆數
            if funder_addr in ["Unknown", "Parse_Error"]:
                continue
                
            # 加入金主中心節點 (First Funder)
            G_for_plot.add_node(funder_addr)
            
            # 動態生成被控制的大戶子錢包，並建立連線以形成「蜘蛛網」結構
            for _ in range(count):
                child_wallet = f"Wallet_Target_{wallet_counter}_{funder_addr[-4:]}"
                G_for_plot.add_node(child_wallet)
                G_for_plot.add_edge(funder_addr, child_wallet)
                wallet_counter += 1

        if G_for_plot.number_of_nodes() == 0:
            continue

        # ── 4. 套用 PyVis 螢光藍/深色風格樣式 ──────────────────────────────
        for node in G_for_plot.nodes():
            short_label = f"{node[:4]}...{node[-4:]}" if len(node) > 15 else str(node)
            degree = G_for_plot.degree[node]
            
            # 設定懸停提示文字 (Hover Text)
            hover_text = f"【完整錢包地址】\n{node}\n\n🔗 關聯大戶數: {degree} 人"
            
            G_for_plot.nodes[node]['label'] = short_label
            G_for_plot.nodes[node]['title'] = hover_text       
            G_for_plot.nodes[node]['size'] = 15 + (degree * 3) 
            G_for_plot.nodes[node]['color'] = '#00BFFF'        
            G_for_plot.nodes[node]['borderWidth'] = 2
            G_for_plot.nodes[node]['shape'] = 'dot'

        # ── 5. 初始化並匯出互動網頁 ───────────────────────────────────────
        net = Network(height="100vh", width="100%", bgcolor="#121212", font_color="#E0E0E0", notebook=False)
        net.from_nx(G_for_plot)
        
        # 設定物理排斥力引擎 (造就完美的蜘蛛網張力)
        net.repulsion(node_distance=300, central_gravity=0.05, spring_length=250, spring_strength=0.03, damping=0.09)
        net.show_buttons(filter_=['physics'])
        
        # 儲存至指定路徑
        html_path = os.path.join(output_dir, f"spider_{coin_name}.html")
        net.save_graph(html_path)
        print(f"✅ [{coin_name}] 蜘蛛網圖生成完畢！")

    print(f"\n🎉 所有蜘蛛網圖已順利寫入：\n{output_dir}")

if __name__ == "__main__":
    generate_spider_web_graphs()