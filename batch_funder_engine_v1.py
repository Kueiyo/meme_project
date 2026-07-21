# ==============================================================================
# 🛠️ 版本狀態：v1（初版 / Legacy Baseline）— 已被 batch_funder_engine_v2.py 取代
# ==============================================================================
# 這個版本單純「往回翻頁找最舊一筆交易」來推定 First Funder，
# 沒有比對 Master CSV 裡的 KOL 推文時間，容易把幾個月後的日常轉帳
# 誤判成「當初建倉的資金來源」。
#
# 新專案請改用 batch_funder_engine_v2.py（T=0 時間錨定版）。
# 本檔案保留僅供比對兩版差異 / 回溯舊資料 (2_data_processed/batch_funder_engine/) 之用。
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
from config import API_KEY

RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"
MAX_TX_LIMIT = 3000

CEX_WALLETS = {
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pT42JA": "Binance",
    "2ojv9BAiHUrvsm9gxDe7fJSzbNZSJcxZvf8dqmWGHG8S": "Binance",
    "5tzFkiKscXHK5ZXCGbXZcmAz51GiyXyVka3YyN4Rz4rD": "OKX",
    "9WzDXwBbmcg8ZTZe1pTPp12338Qne2f51rZ7rU5KUMM4": "KuCoin",
    "Ac5rvv4RXZr9j8jGkXYWbE98kC9F9z2JtZJ8492iP8mY": "Bybit",
    "A77HErqtfN1hLLpvZhb8Qz2n5a7Qp44p83qXz25n61Uq": "Gate.io"
}

# 🚀 高階技術 2: 獨立的智慧請求函數 (具備 Jitter 指數退避)
async def fetch_with_retry(session, payload, max_retries=5):
    for attempt in range(max_retries):
        try:
            async with session.post(RPC_URL, json=payload, timeout=15) as r:
                if r.status == 429:
                    # 加入隨機抖動 (Jitter)，避免多個任務同時甦醒再次撞牆
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

async def get_oldest_signature(session, address, sem):
    async with sem: 
        last_sig = None
        tx_count = 0
        oldest_sig = None

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
                return oldest_sig, tx_count # 遇到極限錯誤，回傳目前找到的最舊進度
                
            results = data.get("result", [])
            if not results:
                break
            
            oldest_sig = results[-1]["signature"]
            last_sig = oldest_sig
            tx_count += len(results)
            
            if len(results) < 1000:
                break

        return oldest_sig, tx_count

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

async def process_wallet(session, address, sem):
    oldest_sig, tx_count = await get_oldest_signature(session, address, sem)
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
    print(f" 🚀 全自動 First Funder 資金溯源引擎 (企業級防禦版)")
    print(f"{'='*60}\n")

    OUTPUT_DIR = os.path.join("2_data_processed", "batch_funder_engine")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open("kind.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 閥門可以稍微開大一點了，因為我們有智慧退避演算法
    sem = asyncio.Semaphore(15)

    # 🚀 高階技術 3: 開啟 TCP 連線池，重複利用網路通道加速
    connector = aiohttp.TCPConnector(limit=50)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if not parts or not parts[0]: continue
            
            coin_name = parts[0]
            output_file = os.path.join(OUTPUT_DIR, f"{coin_name}_funder.json")
            
            # 🚀 高階技術 1: 斷點續傳。如果有這個檔案，直接跳過！
            if os.path.exists(output_file):
                print(f"⏭️ [{coin_name}] 已經掃描完畢，直接跳過 (斷點續傳啟動)！")
                continue

            top50_path = f"1_data_raw/top50_{coin_name}.json"
            if not os.path.exists(top50_path):
                continue

            print(f"\n▶ 正在進行 [{coin_name}] 的 Top 50 大戶資金來源溯源...")
            
            with open(top50_path, "r", encoding="utf-8") as f:
                top50_data = json.load(f)
            
            addresses = [row["address"] for row in top50_data.get("top50", [])]
            
            tasks = [process_wallet(session, addr, sem) for addr in addresses]
            results = await asyncio.gather(*tasks)

            funder_tally = {}
            for res in results:
                funder = res["first_funder"]
                funder_tally[funder] = funder_tally.get(funder, 0) + 1
            
            print(f"   ✅ 完成！共獲取 {len(addresses)} 個錢包，歸納出 {len(funder_tally)} 個獨立資金源頭。")
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "coin": coin_name,
                    "funder_clusters": funder_tally,
                    "wallet_details": results
                }, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(run_batch_processor())