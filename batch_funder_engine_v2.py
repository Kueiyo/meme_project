# ==============================================================================
# 🛠️ 程式演進與修改紀錄 (Version History & Changelog)
# ==============================================================================
# 檔案名稱：batch_funder_engine_v2.py
# 
# 1. 舊版本（batch_funder_engine_v1.py）出現的問題與瓶頸：
#    - 【時間欄位佔位符未實作】：v1 的 anchor_ts 當時僅為預留變數（None），
#      並沒有真正讀取與解析 Master CSV 中的推文時間欄位。
#    - 【CSV 結構不一致與 Missing Data】：Master 總表中，部分幣種有多行 KOL 推文時間，
#      而 WIF、BONK 等大幣區塊的推文時間欄位則為空值 (nan)。若無防呆機制會導致解析崩潰。
#
# 2. 本版本（batch_funder_engine_v2.py）新增的高階功能：
#    - 【強固型 Master CSV 智慧解析器】：自動適應總表複雜的多行結構，
#      支援「Jun 22, 2024」、「2024年10月23日」等多種中英文日期時間格式轉換。
#    - 【最早時間錨定（Earliest T=0）】：自動抓取各幣種所有 KOL 推文中「最早的一篇」
#      作為最精準的創世時間基準（T=0），並自動處理缺失值。
#    - 【時間窗口過濾網】：以 T=0 為基準點，過濾掉發文後期的日常雜訊，精準鎖定建倉期。
# ==============================================================================

import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import asyncio
import aiohttp
import random
import re
from datetime import datetime
import pandas as pd
from config import API_KEY

RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"
MAX_TX_LIMIT = 3000

CEX_WALLETS = {
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pT42JA": "Binance",
    "2ojv9BAiHUrvsm9gxDe7fJSzbNZSJcxZvf8dqmWGHG8S": "Binance",
    "5tzFkiKscXHK5ZXCGbXZcmAz51GiyXyVka3YyN4Rz4rD": "OKX",
    "9WzDXwBbmcg8ZTZe1pTPp12338Qne2f51rZ7rU5KUMM4": "KuCoin",
    "Ac5rvv4RXZr9j8jGkXYWbE98kC9F9z2JtZJ8492iP8mY": "Bybit",
    "A77HErqtfN1hLLpvZhb8Qz2n5a7Qp44p83qXz25n61Uq": "Gate.io",
    "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9": "CEX_HotWallet_A",
    "ASTyfSima4LLAdDgoFGkgqoKowG1LZFDr9fAQrg7iaJZ": "CEX_HotWallet_B",
    "C68a6RCGLiPskbPYtAcsCjhG8tfTWYcoB4JjCrXFdqyo": "CEX_HotWallet_C",
    "9AhKqLR67hwapvG8SA2JFXaCshXc9nALJjpKaHZrsbkw": "CEX_HotWallet_D",
    "EPP7G9CaC9x8EVHnjqLP7F3wJKe1BYXXytF4CSQaFaj9": "CEX_HotWallet_E",
}

def parse_tweet_time_to_timestamp(t_str):
    """將總表中各種奇怪格式的日期字串轉換為 UNIX timestamp"""
    if not isinstance(t_str, str) or 'nan' in t_str:
        return None
    t_str = t_str.strip()
    try:
        parts = t_str.split('·')
        if len(parts) == 2:
            time_part = parts[0].strip().replace('下午', '').replace('上午', '').strip()
            date_part = parts[1].strip()
            
            time_match = re.search(r'(\d{1,2}):(\d{2})', time_part)
            hour, minute = 0, 0
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
            
            if '年' in date_part:
                date_clean = date_part.replace('年', '-').replace('月', '-').replace('日', '')
                dt_str = f"{date_clean} {hour:02d}:{minute:02d}:00"
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                return int(dt.timestamp())
            else:
                dt_str = f"{date_part} {hour:02d}:{minute:02d}:00"
                dt = datetime.strptime(dt_str, "%b %d, %Y %H:%M:%S")
                return int(dt.timestamp())
    except Exception:
        pass
    return None

def load_master_sheet_anchors():
    """解析 Master CSV，回傳每個幣種最早的推文時間戳 (T=0)"""
    master_csv = "master_sheet.csv"
    if not os.path.exists(master_csv):
        return {}
    
    df = pd.read_csv(master_csv, header=None)
    token_anchors = {}
    
    # 區塊定義範圍
    block_ranges = [
        ("HAWK", 3, 11), ("LIBRA", 12, 17), ("SHAR", 18, 22),
        ("QUANT", 23, 26), ("TRUMP", 27, 34), ("MELANIA", 35, 46),
        ("YZY", 47, 55), ("M3M3", 56, 63), ("CATFI", 64, 64), ("CONDOM", 65, 66)
    ]
    
    for sym, start_r, end_r in block_ranges:
        timestamps = []
        for r in range(start_r, min(end_r + 1, len(df))):
            t_val = df.iloc[r, 9] # col 9 is kol_tweet_time_utc
            ts = parse_tweet_time_to_timestamp(t_val)
            if ts:
                timestamps.append(ts)
        if timestamps:
            token_anchors[sym] = min(timestamps) # 取最早的一篇作為 T=0
            
    return token_anchors

async def fetch_with_retry(session, payload, max_retries=5):
    for attempt in range(max_retries):
        try:
            async with session.post(RPC_URL, json=payload, timeout=15) as r:
                if r.status == 429:
                    sleep_time = (2 ** attempt) + random.uniform(0.1, 1.5)
                    await asyncio.sleep(sleep_time)
                    continue
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            if attempt == max_retries - 1:
                return {"error": str(e)}
            await asyncio.sleep(1 + random.uniform(0, 1))
    return {"error": "Max retries reached"}

async def get_oldest_signature_with_anchor(session, address, anchor_timestamp, sem):
    """帶有 T=0 時間錨點的溯源函數"""
    async with sem:
        last_sig = None
        tx_count = 0
        candidates = []

        while tx_count < MAX_TX_LIMIT:
            params = [address, {"limit": 1000}]
            if last_sig:
                params[1]["before"] = last_sig

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": params
            }

            data = await fetch_with_retry(session, payload)
            if "error" in data:
                break
                
            results = data.get("result", [])
            if not results:
                break
            
            for tx in results:
                sig = tx.get("signature")
                b_time = tx.get("blockTime")
                if sig:
                    candidates.append((sig, b_time))
            
            last_sig = results[-1]["signature"]
            tx_count += len(results)
            
            if len(results) < 1000:
                break

        if not candidates:
            return None, tx_count

        # 如果有設定 T=0 錨點時間，篩選出小於或接近 T=0 7天內的創世交易
        if anchor_timestamp:
            filtered = [c for c in candidates if c[1] and c[1] <= anchor_timestamp + 86400 * 7]
            if filtered:
                return filtered[-1][0], tx_count

        return candidates[-1][0], tx_count

async def get_funder_from_signature(session, signature):
    if not signature: return "Unknown"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
        ]
    }
    
    data = await fetch_with_retry(session, payload)
    tx_data = data.get("result")
    if not tx_data: return "Unknown"

    try:
        account_keys = tx_data["transaction"]["message"]["accountKeys"]
        for account in account_keys:
            if account.get("signer"):
                return account["pubkey"]
        return account_keys[0]["pubkey"]
    except:
        return "Parse_Error"

async def process_wallet(session, address, anchor_ts, sem):
    oldest_sig, tx_count = await get_oldest_signature_with_anchor(session, address, anchor_ts, sem)
    funder = await get_funder_from_signature(session, oldest_sig)
    cex_label = CEX_WALLETS.get(funder, "Private_Wallet")
    
    return {
        "address": address,
        "tx_scanned": tx_count,
        "first_funder": funder,
        "source_type": cex_label
    }

async def run_batch_processor():
    print(f"\n{'='*60}")
    print(f" 🚀 全自動 First Funder 資金溯源引擎 v2 (Master CSV 智慧時間解析版)")
    print(f"{'='*60}\n")

    # 載入時間錨點
    token_anchors = load_master_sheet_anchors()
    print(f"✅ 成功從 Master CSV 解析出 {len(token_anchors)} 個代幣的 T=0 錨點時間！")

    OUTPUT_DIR = os.path.join("2_data_processed", "batch_funder_engine_v2")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sem = asyncio.Semaphore(15)
    connector = aiohttp.TCPConnector(limit=50)

    if os.path.exists("kind.txt"):
        with open("kind.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = []

    async with aiohttp.ClientSession(connector=connector) as session:
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if not parts or not parts[0]: continue
            
            coin_name = parts[0]
            output_file = os.path.join(OUTPUT_DIR, f"{coin_name}_funder.json")
            
            if os.path.exists(output_file):
                print(f"⏭️ [{coin_name}] 已經掃描完畢，直接跳過 (斷點續傳)！")
                continue

            top50_path = f"1_data_raw/top50_{coin_name}.json"
            if not os.path.exists(top50_path):
                continue

            # 抓取該幣對應的 T=0 錨點時間戳 (若無則為 None)
            anchor_ts = token_anchors.get(coin_name)
            anchor_str = datetime.fromtimestamp(anchor_ts).strftime('%Y-%m-%d %H:%M') if anchor_ts else "無錨點(預設回溯)"
            
            print(f"\n▶ 正在進行 [{coin_name}] 溯源 | T=0 錨點: {anchor_str}")
            
            with open(top50_path, "r", encoding="utf-8") as f:
                top50_data = json.load(f)
            
            addresses = [row["address"] for row in top50_data.get("top50", [])]
            
            tasks = [process_wallet(session, addr, anchor_ts, sem) for addr in addresses]
            results = await asyncio.gather(*tasks)

            funder_tally = {}
            for res in results:
                funder = res["first_funder"]
                funder_tally[funder] = funder_tally.get(funder, 0) + 1
            
            print(f"   ✅ 完成！歸納出 {len(funder_tally)} 個獨立資金源頭。")
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "coin": coin_name,
                    "anchor_timestamp": anchor_ts,
                    "funder_clusters": funder_tally,
                    "wallet_details": results
                }, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(run_batch_processor())