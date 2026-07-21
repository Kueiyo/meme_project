import requests
import json
import networkx as nx
import matplotlib.pyplot as plt
import os
import time  
import asyncio
import aiohttp
from pyvis.network import Network
from config import API_KEY
from requests.exceptions import ReadTimeout, ConnectionError

def run(coin_name, dir_raw, dir_processed, dir_img, dir_html):
    # ── 參數設定 ──
    SCALES       = [10, 50, 100, 500, 1000]
    EARLY_SCALES = [10, 50, 100, 500, 1000]
    max_scale       = max(SCALES)
    max_early_scale = max(EARLY_SCALES)
    
    URL          = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"
    IDENTITY_URL = f"https://api.helius.xyz/v1/wallet/batch-identity?api-key={API_KEY}"

    # 傳統同步 RPC (用來抓名單、抓單一資料，維持輕量)
    def rpc(method, params, retries=3):
        for attempt in range(retries):
            try:
                r = requests.post(URL, json={
                    "jsonrpc": "2.0", "id": "1",
                    "method": method, "params": params
                }, timeout=30)
                r.raise_for_status()
                return r.json().get("result")
            except (ReadTimeout, ConnectionError, requests.exceptions.HTTPError) as e:
                print(f"      ⚠️ 同步 API 異常 ({type(e).__name__})，等待 3 秒後重試...")
                time.sleep(3)
        return None

    # 🚀🚀🚀 核心非同步併發引擎 (放棄陣列打包，改用高頻單點突破) 🚀🚀🚀
    async def fetch_transactions_async(signatures, max_concurrent=15):
        parsed_transactions = []
        
        # 限制底層連線數，避免把自己的網卡與 RPC 塞爆
        connector = aiohttp.TCPConnector(limit=max_concurrent)
        async with aiohttp.ClientSession(connector=connector) as session:
            sem = asyncio.Semaphore(max_concurrent)
            
            async def fetch_single(sig):
                payload = {
                    "jsonrpc": "2.0", 
                    "id": "1", 
                    "method": "getTransaction", 
                    "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
                }
                
                async with sem:
                    # 導入 Exponential Backoff (指數退避演算法)
                    for attempt in range(4): 
                        try:
                            async with session.post(URL, json=payload, timeout=20) as r:
                                if r.status == 429:
                                    # 撞到速率限制 (Rate Limit)，乖乖退避
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                                r.raise_for_status()
                                data = await r.json()
                                return data.get("result")
                        except Exception as e:
                            # 抓取真實的 HTTP 狀態碼，讓我們知道死因
                            status = getattr(e, 'status', 'Unknown')
                            if attempt == 3:
                                print(f"      ⚠️ 解析失敗 (HTTP {status}): {type(e).__name__}")
                            await asyncio.sleep(1.5 ** attempt) # 失敗越多次，等越久
                    
                    return None

            # 建立所有任務，同時發射！
            tasks = [fetch_single(sig) for sig in signatures]
            results = await asyncio.gather(*tasks)
            
            # 過濾掉失敗的 (None)，把成功的加入清單
            for res in results:
                if res:
                    parsed_transactions.append(res)
                            
        return parsed_transactions
    # 🚀🚀🚀 引擎結束 🚀🚀🚀

    input_path = f"{dir_raw}/top50_{coin_name}.json"
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"找不到原始資料檔 {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    top50_list   = data["top50"]
    total_supply = data["total_supply"]
    MINT         = data["mint"]
    top50_addrs  = set(row["address"] for row in top50_list)

    print(f"=== {coin_name} 指標計算 ===\n")
    concentration = data["top50_concentration"]
    print(f"① top50_concentration = {concentration:.6f}")

    # ════════════════════════════════════════════════
    # 指標二：多尺度群聚係數 (加上非同步快取機制)
    # ════════════════════════════════════════════════
    print(f"\n② 建錢包關聯圖（每個地址最多查 {max_scale} 筆交易，計算尺度 {SCALES}）...")
    
    cache_path = f"{dir_raw}/cache_tx_{coin_name}.json"
    address_history = {}

    if os.path.exists(cache_path):
        print("   📦 發現本地快取檔案！直接讀取，節省大量 API Token...")
        with open(cache_path, "r", encoding="utf-8") as f:
            address_history = json.load(f)
    else:
        print("   🌐 無本地快取，啟動非同步批次引擎向 API 請求歷史交易...")
        start_time = time.time()
        
        address_history = {addr: [] for addr in top50_addrs}
        for i, row in enumerate(top50_list, 1):
            addr = row["address"]
            # 1. 先同步抓取最多 1000 筆簽名檔 (這個 API 很快)
            sig_result = rpc("getSignaturesForAddress", [addr, {"limit": max_scale}])
            if not sig_result: continue
            
            signatures = [tx["signature"] for tx in sig_result]
            
            # 2. 啟動非同步引擎，光速批次下載這 1000 筆的詳細內容
            parsed_txs = asyncio.run(fetch_transactions_async(signatures))
            
            # 3. 處理關聯網路
            for tx in parsed_txs:
                involved_addrs = set()
                for key in tx.get("transaction", {}).get("message", {}).get("accountKeys", []):
                    other = key.get("pubkey", "") if isinstance(key, dict) else key
                    if other in top50_addrs and other != addr:
                        involved_addrs.add(other)
                address_history[addr].append(list(involved_addrs))

            print(f"   ⚡ {i}/50 完成 (共抓取 {len(address_history[addr])} 筆有效紀錄)")
        
        print(f"   ⏱️ 群聚資料抓取完成，耗時: {time.time() - start_time:.2f} 秒")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(address_history, f)
        print(f"   💾 歷史交易已快取至 {cache_path}")

    # --- 群聚係數計算邏輯 ---
    clustering_results = {}
    G_for_plot = nx.Graph()

    for scale in SCALES:
        G_scale = nx.Graph()
        G_scale.add_nodes_from(top50_addrs)
        for addr, history in address_history.items():
            for involved_addrs in history[:scale]:
                for other in involved_addrs:
                    G_scale.add_edge(addr, other)
        try:
            c_val = nx.average_clustering(G_scale)
        except Exception:
            c_val = 0.0
            
        clustering_results[f"scale_{scale}"] = round(c_val, 6)
        print(f"   - 尺度 {scale} 筆: 群聚係數 = {c_val:.6f} (連線數: {G_scale.number_of_edges()})")
        if scale == max_scale: G_for_plot = G_scale

    clustering = clustering_results.get("scale_100", 0.0)

    # ─── 繪圖與存檔區 ───
    print("\n正在繪製靜態與動態關係圖並存檔...")
    plt.figure(figsize=(14, 14))
    labels = {node: f"{node[:4]}...{node[-4:]}" if isinstance(node, str) and len(node)>8 else str(node) for node in G_for_plot.nodes()}
    nx.draw(G_for_plot, labels=labels, with_labels=True, font_size=8, font_color="black", node_size=100, node_color="skyblue", edge_color="gray", alpha=0.7)              
    plt.title(f"{coin_name} Top 50 Wallets Network (Max Scale: {max_scale} TXs)")
    plt.savefig(f"{dir_img}/graph_{coin_name}.png", dpi=300, bbox_inches='tight')  
    plt.close()

    print("正在優化並生成動態互動網頁 (HTML)...")
    for node in G_for_plot.nodes():
        short_label = f"{node[:4]}...{node[-4:]}" if len(node) > 8 else str(node)
        degree = G_for_plot.degree[node]
        hover_text = f"【完整錢包地址】\n{node}\n\n🔗 關聯大戶數: {degree} 人"
        G_for_plot.nodes[node]['label'] = short_label
        G_for_plot.nodes[node]['title'] = hover_text       
        G_for_plot.nodes[node]['size'] = 15 + (degree * 3) 
        G_for_plot.nodes[node]['color'] = '#00BFFF'        
        G_for_plot.nodes[node]['borderWidth'] = 2
        G_for_plot.nodes[node]['shape'] = 'dot'

    net = Network(height="100vh", width="100%", bgcolor="#121212", font_color="#E0E0E0", notebook=False)
    net.from_nx(G_for_plot)
    net.repulsion(node_distance=300, central_gravity=0.05, spring_length=250, spring_strength=0.03, damping=0.09)
    net.show_buttons(filter_=['physics'])
    
    html_path = f"{dir_html}/graph_{coin_name}.html"
    net.save_graph(html_path)
    print(f"✅ 高質感互動網頁已存檔：{html_path}")

    # ════════════════════════════════════════════════
    # 指標三：多尺度早鳥比例 (非同步重構)
    # ════════════════════════════════════════════════
    print(f"\n③ 抓最早 {max_early_scale} 筆交易（計算尺度 {EARLY_SCALES}）...")
    
    cache_early_path = f"{dir_raw}/cache_early_{coin_name}.json"
    early_addresses_ordered = []

    if os.path.exists(cache_early_path):
        print("   📦 發現本地早鳥快取檔案！直接讀取真實創世資料...")
        with open(cache_early_path, "r", encoding="utf-8") as f:
            early_addresses_ordered = json.load(f)
    else:
        print("   🌐 無本地快取，啟動分頁回溯演算法尋找創世區塊...")
        all_signatures = []
        last_signature = None
        page = 1
        
        while True:
            params = [{"limit": 1000}]
            if last_signature: params[0]["before"] = last_signature
            sig_result = rpc("getSignaturesForAddress", [MINT, params[0]])
            if not sig_result: break 
                
            all_signatures.extend(sig_result)
            last_signature = sig_result[-1]["signature"]
            print(f"      - 已向下挖掘 {page * 1000} 筆歷史簽名...")
            page += 1
            if page > 100:
                print("      ⚠️ 歷史紀錄過長，已達到 10 萬筆安全上限。")
                break 

        if all_signatures:
            true_early_signatures_info = list(reversed(all_signatures[-max_early_scale:]))
            true_early_signatures = [tx["signature"] for tx in true_early_signatures_info]
            
            print(f"   🔍 定位創世區塊！啟動非同步引擎解析這 {len(true_early_signatures)} 筆早鳥交易...")
            start_time = time.time()
            
            parsed_early_txs = asyncio.run(fetch_transactions_async(true_early_signatures))
            
            for tx in parsed_early_txs:
                involved_in_tx = []
                for key in tx.get("transaction", {}).get("message", {}).get("accountKeys", []):
                    addr = key.get("pubkey", "") if isinstance(key, dict) else key
                    if addr: involved_in_tx.append(addr)
                early_addresses_ordered.append(involved_in_tx)
            
            print(f"   ⏱️ 早鳥資料解析完成，耗時: {time.time() - start_time:.2f} 秒")
            with open(cache_early_path, "w", encoding="utf-8") as f:
                json.dump(early_addresses_ordered, f)
            print(f"   💾 真實早鳥交易已快取至 {cache_early_path}")
        else:
            print("   ⚠️ 找不到任何早期交易紀錄。")

    # --- 早鳥佔比計算邏輯 ---
    early_addresses = set()
    early_results = {}

    for idx, addrs_in_tx in enumerate(early_addresses_ordered, 1):
        early_addresses.update(addrs_in_tx)
        if idx in EARLY_SCALES:
            early_in_top50 = top50_addrs & early_addresses
            ratio = len(early_in_top50) / len(top50_list) if len(top50_list) > 0 else 0
            early_results[f"scale_{idx}"] = round(ratio, 6)
            print(f"   - 尺度 {idx} 筆: 早鳥佔比 = {ratio:.6f} ({len(early_in_top50)}/50)")

    final_ratio = 0.0
    if early_addresses_ordered:
        final_early_in_top50 = top50_addrs & early_addresses
        final_ratio = len(final_early_in_top50) / len(top50_list) if len(top50_list) > 0 else 0

    for scale in EARLY_SCALES:
        if f"scale_{scale}" not in early_results:
            early_results[f"scale_{scale}"] = round(final_ratio, 6)

    early_ratio = early_results.get("scale_100", 0.0)

    # ════════════════════════════════════════════════
    # 指標四：CEX 身份查核
    # ════════════════════════════════════════════════
    print(f"\n④ 查 CEX 身份...")
    cex_found = []

    try:
        resp = requests.post(IDENTITY_URL, json={"addresses": list(top50_addrs)}, timeout=30).json()
        if isinstance(resp, list):
            for item in resp:
                cat, typ, name, addr = item.get("category", ""), item.get("type", ""), item.get("name", ""), item.get("address", "")
                if cat == "Centralized Exchange" or typ == "exchange" or any(x in name.lower() for x in ["binance", "coinbase", "okx", "kraken", "bybit", "kucoin", "gate", "mexc"]):
                    cex_found.append((addr, name))
                    print(f"   → [API 識別] CEX 地址：{addr}  ({name})")
        else:
            print(f"   ⚠️ Helius Identity API 無法查詢: {resp.get('error', 'Unknown Error')}")
    except Exception as e:
        print(f"   ⚠️ Helius API 呼叫失敗: {e}")

    KNOWN_CEX_WALLETS = {
        "5tzFkiKscXHK5ZXCGbXZcmAz4ZQzASVwcxKVAyJC1v": "Binance Hot",
        "2ojv9BAiHUrvsm9gxDe7fJSzbNZALG4ebUxbkKwHEn": "Binance Hot",
        "AC5RDfQFmDS1deWZos921FZJjcWNNWwqoA95XW9A2k": "Binance Hot",
        "5WspZhaGEXo7h3X7v2DDEB6K8Mv1jR1i7J8fBv4x3r": "OKX Hot",
        "5VCwKtCXgCJ6kit5FybXjvriW3x33m2yvH2hB3QkGv": "Bybit Hot",
        "FWznbcNXWQuHTawe9RxvQ2LdCENoTf7snZcAEZ1nCq": "Kraken Hot",
        "A77HErqtfNhmQhQEXQnL1P1b25n1uW8Uhw2Gpx6E5w": "KuCoin Hot",
        "HXsKP7wrBWaQ8T2Vtjry3Nj3oUgwYcqq9vrHDM12G6": "Gate.io Hot"
    }

    for addr in top50_addrs:
        if addr in KNOWN_CEX_WALLETS:
            if not any(addr == existing[0] for existing in cex_found):
                name = KNOWN_CEX_WALLETS[addr]
                cex_found.append((addr, name))
                print(f"   → [本地名單識別] CEX 地址：{addr} ({name})")

    cex_count = len(cex_found)
    print(f"④ cex_wallet_count = {cex_count}")

    metrics = {
        "coin":                   coin_name,
        "top50_concentration":    round(concentration, 6),
        "clustering_coefficient": round(clustering, 6),
        "clustering_details":     clustering_results,
        "early_buyers_ratio":     round(early_ratio, 6),
        "early_buyers_details":   early_results,
        "cex_wallet_count":       cex_count,
    }

    output_path = f"{dir_processed}/metrics_{coin_name}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"✅ JSON 指標已存檔：{output_path}")