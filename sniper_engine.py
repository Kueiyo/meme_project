import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import asyncio
import aiohttp
from config import API_KEY

# ════════════════════════════════════════════════
# ⚙️ 狙擊槍設定區
# ════════════════════════════════════════════════
# 往前狙擊的區塊數量 (包含創世區塊本身，5 代表抓開盤後約 2 秒鐘的交易)
SNIPE_BLOCKS_COUNT = 5 
URL = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"

async def fetch_block(session, block_number, retries=3):
    """取得單一區塊的所有詳細交易內容"""
    payload = {
        "jsonrpc": "2.0",
        "id": str(block_number),
        "method": "getBlock",
        "params": [
            block_number,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0,
                "transactionDetails": "full",
                "rewards": False
            }
        ]
    }
    
    for attempt in range(retries):
        try:
            async with session.post(URL, json=payload, timeout=30) as r:
                if r.status == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                data = await r.json()
                if "result" in data and data["result"]:
                    return data["result"]
                elif "error" in data:
                    print(f"      ⚠️ 區塊 {block_number} 讀取錯誤: {data['error'].get('message')}")
                    return None
        except Exception as e:
            await asyncio.sleep(1.5)
    return None

async def run_sniper():
    print(f"\n{'='*60}")
    print(f" 🎯 創世老鼠倉狙擊系統 (Block Sniper Engine) 啟動")
    print(f"{'='*60}\n")

    if not os.path.exists("kind_sniper.txt"):
        print("❌ 找不到 kind_sniper.txt！請確保檔案存在。")
        return

    with open("kind_sniper.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    async with aiohttp.ClientSession() as session:
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3: continue
            
            coin_name, mint_address, birth_block_str = parts[0], parts[1], parts[2]
            
            if birth_block_str == "???" or not birth_block_str.isdigit():
                print(f"⏭️ [{coin_name}] 尚未填寫有效的創世區塊，跳過狙擊。")
                continue

            birth_block = int(birth_block_str)
            # 🎯 【新增防呆】：防止程式去抓 2020 年的第 0 號區塊
            if birth_block == 0:
                print(f"⏭️ [{coin_name}] 創世區塊標記為 0 (無明確流動性池紀錄)，自動跳過。")
                continue
            print(f"\n▶ 開始狙擊 {coin_name} (合約: {mint_address[:6]}...{mint_address[-4:]})")
            print(f"   降落目標：第 {birth_block} 區塊")

            # 讀取 Step 1 的 Top 50 名單來做比對
            top50_path = f"1_data_raw/top50_{coin_name}.json"
            if not os.path.exists(top50_path):
                print(f"   ⚠️ 找不到 {top50_path}，請先執行一般管線獲取 Top 50 名單。")
                continue
                
            with open(top50_path, "r", encoding="utf-8") as f:
                top50_data = json.load(f)
            top50_addrs = set(row["address"] for row in top50_data["top50"])

            # 準備動態擴展抓取
            genesis_buyers = set()
            total_txs_scanned = 0
            current_block = birth_block
            blocks_scanned = 0
            
            # 🎯 【全新設定：人數優先】
            TARGET_BUYERS = 1000
            MAX_BLOCK_LIMIT = 5000  # 安全極限拉高到 5000 區塊 (約 33 分鐘)，給足時間找人

            print(f"   🌐 啟動 [人數優先] 拖網雷達 (目標: 收集 {TARGET_BUYERS} 個真實買家)...")

            while True:
                # 🚀 引擎催落去：一次併發 50 個區塊！(速度提升 5 倍)
                batch_size = 50
                blocks_to_fetch = [current_block + i for i in range(batch_size)]
                
                tasks = [fetch_block(session, b) for b in blocks_to_fetch]
                blocks_data = await asyncio.gather(*tasks)

                for i, block_result in enumerate(blocks_data):
                    if not block_result or "transactions" not in block_result:
                        continue
                    
                    txs = block_result["transactions"]
                    total_txs_scanned += len(txs)
                    
                    for tx in txs:
                        meta = tx.get("meta") or {}
                        msg = tx.get("transaction", {}).get("message", {})
                        account_keys = msg.get("accountKeys", [])
                        
                        involved_keys = [k["pubkey"] if isinstance(k, dict) else k for k in account_keys]
                        
                        # 🎯 抓取真實發起交易的 Signer
                        signers = [k["pubkey"] for k in account_keys if isinstance(k, dict) and k.get("signer")]
                        if not signers and isinstance(account_keys[0], str):
                            signers = [account_keys[0]]
                        
                        # 過濾邏輯：必須碰到合約，且確實有 Token 餘額變動
                        if mint_address in involved_keys and meta.get("postTokenBalances"):
                            for signer in signers:
                                genesis_buyers.add(signer)

                # 推進區塊進度
                current_block += batch_size
                blocks_scanned += batch_size
                
                print(f"      - 已推進 {blocks_scanned} 區塊 | 目前收集到 {len(genesis_buyers)} 個真實買家")

                # ⚖️ 【最新判斷邏輯：只看人數】
                if len(genesis_buyers) >= TARGET_BUYERS:
                    print(f"   ✅ 達標！成功收集到 {len(genesis_buyers)} 個早期參與者。")
                    break
                
                # 安全煞車：避免這個幣真的沒人買 (死盤)，導致無限消耗 API
                elif blocks_scanned >= MAX_BLOCK_LIMIT:
                    print(f"   ⚠️ 觸發極限煞車 ({MAX_BLOCK_LIMIT} 區塊)。這個幣可能開盤後買氣極低，強制結算。")
                    break

            print(f"   🔍 掃描完畢！共檢查了 {total_txs_scanned} 筆交易。")
            print(f"   ⚡ 總共收集到 {len(genesis_buyers)} 個早期持有者錢包。")

            # 🔥 關鍵比對：這些創世錢包，有誰現在還坐在 Top 50 的席位裡？
            rats = top50_addrs.intersection(genesis_buyers)
            
            if rats:
                print(f"\n   🚨 【抓到老鼠倉 / 內部錢包】🚨")
                print(f"   發現 {len(rats)} 個錢包從開盤第 1 秒持有到現在，並且名列 Top 50 大戶！")
                for rank, row in enumerate(top50_data["top50"], 1):
                    if row["address"] in rats:
                        print(f"      🐀 排名 #{rank:02d} | 地址: {row['address']} | 餘額: {row['balance']:,}")
            else:
                print(f"\n   ✅ 該幣的 Top 50 大戶，皆不在最早期進場的 {len(genesis_buyers)} 人名單中。")

            # 將結果存檔 (你可以後續寫入你的報表)
            snipe_result = {
                "coin": coin_name,
                "birth_block": birth_block,
                "genesis_wallets_count": len(genesis_buyers),
                "rat_wallets_in_top50": list(rats)
            }
            # 🔥 確保資料目錄結構正確
            SNIPER_DIR = "2_data_processed/sniper_results"
            os.makedirs(SNIPER_DIR, exist_ok=True) # 這是關鍵：自動建立子資料夾
            
            # 建立完整的檔案路徑 (存入 sniper_results 資料夾內)
            output_filename = os.path.join(SNIPER_DIR, f"sniper_result_{coin_name}.json")
            
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(snipe_result, f, indent=2)
                
            print(f"✅ 狙擊資料已存檔至：{output_filename}")

if __name__ == "__main__":
    # 使用 asyncio 啟動狙擊引擎
    asyncio.run(run_sniper())