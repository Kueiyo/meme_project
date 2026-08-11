import requests
import json
import os
from datetime import datetime, timezone
from config import API_KEY

def run(coin_name, mint_address, event_time_str, window_minutes, dir_raw, dir_processed):
    # ── 1. 時間格式轉換 (處理 Twitter 時間字串) ──
    # 假設 CSV 中的時間格式為 "08:10 · Jun 22, 2024"
    try:
        # 將字串轉換為 Unix Timestamp (UTC)
        dt = datetime.strptime(event_time_str, "%H:%M · %b %d, %Y")
        target_ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        print(f"❌ 時間格式解析失敗：{event_time_str}。請確認是否為 'HH:MM · Mmm DD, YYYY' 格式。")
        return

    window_sec = window_minutes * 60
    start_ts = target_ts - window_sec
    end_ts = target_ts + window_sec

    print(f"\n=== {coin_name} 事件分析 (KOL 喊盤/發布) ===")
    print(f"🎯 目標時間: {dt} UTC")
    print(f"🔍 觀測區間: ±{window_minutes} 分鐘 (Timestamp: {start_ts} ~ {end_ts})")

    URL = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"

    def rpc(method, params):
        r = requests.post(URL, json={"jsonrpc": "2.0", "id": "1", "method": method, "params": params}, timeout=30)
        return r.json().get("result")

    # ── 2. 本地快取機制防護 ──
    # 命名加上 timestamp，如果未來你換了時間點，會自動抓新資料，不會讀到舊的
    cache_file = f"{dir_raw}/event_txs_{coin_name}_{target_ts}.json"
    event_txs = []

    if os.path.exists(cache_file):
        print("   📦 發現本地事件快取！直接讀取，0 API 消耗...")
        with open(cache_file, "r", encoding="utf-8") as f:
            event_txs = json.load(f)
    else:
        print("   🌐 無快取，啟動【時間跳躍掃描演算法】尋找目標時間段...")
        
        last_sig = None
        relevant_signatures = []
        page = 1
        skipped_txs = 0

        # 【第一階段：只看目錄，跳躍翻頁】
        while True:
            params = [{"limit": 1000}]
            if last_sig:
                params[0]["before"] = last_sig
                
            sigs = rpc("getSignaturesForAddress", [mint_address, params[0]])
            if not sigs:
                break
                
            newest_time = sigs[0].get("blockTime", 0)
            oldest_time = sigs[-1].get("blockTime", 0)
            
            # 情況 A：這整頁的交易都比我們的「觀測結束時間」還要新 (還在未來)
            if oldest_time > end_ts:
                skipped_txs += len(sigs)
                print(f"      ⏩ 第 {page} 頁時間較新 ({datetime.fromtimestamp(oldest_time)})，跳過 1000 筆...")
                last_sig = sigs[-1]["signature"]
                page += 1
                continue
                
            # 情況 B：這整頁的交易都比我們的「觀測開始時間」還要舊 (已過頭)
            if newest_time < start_ts:
                print(f"      🛑 第 {page} 頁時間已過舊 ({datetime.fromtimestamp(newest_time)})，停止掃描。")
                break
                
            # 情況 C：命中觀測區間！將符合時間的簽名萃取出來
            for s in sigs:
                t = s.get("blockTime", 0)
                if start_ts <= t <= end_ts:
                    relevant_signatures.append(s["signature"])
            
            last_sig = sigs[-1]["signature"]
            page += 1

        print(f"   🎯 掃描完畢！成功略過 {skipped_txs} 筆無關交易 (為您省下 {skipped_txs} 次 API 呼叫)。")
        print(f"   🔍 鎖定區間內共有 {len(relevant_signatures)} 筆交易，開始解析內容...")

        # 【第二階段：精準打擊，只抓目標區間的交易細節】
        for idx, sig in enumerate(relevant_signatures, 1):
            tx = rpc("getTransaction", [sig, {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0
            }])
            if tx:
                event_txs.append(tx)
            
            if idx % 50 == 0:
                print(f"      - 解析進度: {idx}/{len(relevant_signatures)}...")

        # 寫入快取
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(event_txs, f)
        print(f"   💾 事件交易已快取至 {cache_file}")

    # ── 3. 策略分析：與 Top 50 大戶進行比對 (抓老鼠倉與倒貨主力) ──
    top50_path = f"{dir_raw}/top50_{coin_name}.json"
    if not os.path.exists(top50_path):
        print(f"   ⚠️ 找不到 {top50_path}，無法進行大戶比對。請先執行 Step 1。")
        return

    with open(top50_path, "r", encoding="utf-8") as f:
        top50_addrs = set(row["address"] for row in json.load(f)["top50"])

    active_top50_in_window = set()
    
    # 掃描目標區間內的所有交易，尋找是否有 Top 50 大戶的身影
    for tx in event_txs:
        for key in tx.get("transaction", {}).get("message", {}).get("accountKeys", []):
            addr = key.get("pubkey", "") if isinstance(key, dict) else key
            if addr in top50_addrs:
                active_top50_in_window.add(addr)

    print(f"\n   🚨 【內線/倒貨雷達】分析結果 🚨")
    print(f"   在 KOL 發布事件的 ±{window_minutes} 分鐘內，共有 {len(active_top50_in_window)} 位 Top 50 大戶進行了交易！")
    
    if active_top50_in_window:
        print("   可疑大戶名單：")
        for addr in active_top50_in_window:
            print(f"   - {addr}")
            
    # 輸出分析報告到 processed 資料夾
    report = {
        "coin": coin_name,
        "event_time_utc": event_time_str,
        "window_minutes": window_minutes,
        "total_txs_in_window": len(event_txs),
        "suspicious_whales_count": len(active_top50_in_window),
        "suspicious_whales_addresses": list(active_top50_in_window)
    }
    
    out_path = f"{dir_processed}/event_report_{coin_name}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"✅ 事件分析報告已存檔：{out_path}")