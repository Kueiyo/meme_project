import requests
import json
from config import API_KEY

def run(coin_name, mint_address, dir_raw):
    URL = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"

    def rpc(method, params):
        r = requests.post(URL, json={
            "jsonrpc": "2.0", "id": "1",
            "method": method, "params": params
        }, timeout=60)
        return r.json()["result"]

    print(f"抓 {coin_name} 前 50 大持有人（共 3 次 API 呼叫）...")

    # ── 第 1 次：前 20 大（官方方法，已排序）─────────────────
    top20_raw = rpc("getTokenLargestAccounts", [mint_address])["value"]
    top20_addresses = set(a["address"] for a in top20_raw)

    # ── 第 2 次：抓第一頁 1000 筆，補到 50 名 ───────────────
    res = requests.post(URL, json={
        "jsonrpc": "2.0", "id": "1",
        "method": "getTokenAccounts",
        "params": {"mint": mint_address, "limit": 1000}
    }, timeout=60).json()

    extra_holders = {}
    for a in res.get("result", {}).get("token_accounts", []):
        owner  = a.get("owner", "")
        amount = int(a.get("amount") or 0)
        addr   = a.get("address", "")
        # 跳過已在 top20 裡的、餘額為 0 的
        if addr and addr not in top20_addresses and amount > 0:
            extra_holders[addr] = extra_holders.get(addr, 0) + amount

    # 從剩下的裡面取排名 21～50
    extra_top30 = sorted(extra_holders.items(), key=lambda x: x[1], reverse=True)[:30]

    # ── 第 3 次：總供給 ──────────────────────────────────────
    total_supply = int(rpc("getTokenSupply", [mint_address])["value"]["amount"])

    # ── 合併、重新排序 ────────────────────────────────────────
    all_holders = (
        [(a["address"], int(a["amount"])) for a in top20_raw] +
        list(extra_top30)
    )
    all_holders.sort(key=lambda x: x[1], reverse=True)
    top50 = all_holders[:50]

    # ── 計算佔比 ─────────────────────────────────────────────
    top50_sum     = sum(bal for _, bal in top50)
    concentration = top50_sum / total_supply

    # ── 印出結果 ─────────────────────────────────────────────
    print(f"\n總供給：{total_supply:,}")
    print(f"top50_concentration = {concentration:.6f}  ({concentration*100:.2f}%)")
    print(f"\n前 50 大持有人：")
    for i, (addr, bal) in enumerate(top50, 1):
        pct = bal / total_supply * 100
        print(f"  {i:>2}. {addr}  {pct:.4f}%")

    # ── 存檔 ─────────────────────────────────────────────────
    output = {
        "coin": coin_name,
        "mint": mint_address,
        "total_supply": total_supply,
        "top50_concentration": round(concentration, 6),
        "top50": [{"rank": i+1, "address": addr, "balance": bal}
                  for i, (addr, bal) in enumerate(top50)]
    }
    
    # 使用傳入的 dir_raw 路徑來存檔
    output_path = f"{dir_raw}/top50_{coin_name}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ 已存檔：{output_path}")