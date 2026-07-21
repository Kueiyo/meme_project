import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import step1_fetch_top50 as step1
import step2_calc_metrics as step2
import step3_generate_report as step3
import step4_event_analysis as step4


# ════════════════════════════════════════════════
# ⚙️ 系統執行總開關
# ════════════════════════════════════════════════
RUN_STEP_1 = True
RUN_STEP_2 = True
RUN_STEP_3 = True
RUN_STEP_4 = False  

# 🎯 【新增】指定從哪個幣開始跑？如果是 None，就從頭開始跑。
START_FROM_COIN = "MELANIA"
FORCE_OVERWRITE = True
# 設定觀測時間區間 (分鐘)
STEP_4_WINDOW = 30 


DIR_RAW = "1_data_raw"
DIR_PROCESSED = "2_data_processed"
DIR_TXT = "3_reports_txt"
DIR_IMG = "4_reports_img"
DIR_HTML = "5_reports_html"

for d in [DIR_RAW, DIR_PROCESSED, DIR_TXT, DIR_IMG, DIR_HTML]:
    os.makedirs(d, exist_ok=True)

def main():
    kind_file = "kind.txt"
    if not os.path.exists(kind_file):
        print(f"❌ 找不到 {kind_file}！")
        return

    with open(kind_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    has_reached_start = False if START_FROM_COIN else True

    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2: continue 
        
        coin_name, mint_address = parts[0], parts[1]
        event_time = parts[2] if len(parts) > 2 else None

        # 🎯 【新增】尋找起點邏輯
        if not has_reached_start:
            if coin_name == START_FROM_COIN:
                has_reached_start = True # 找到了，解除封印開始跑！
            else:
                continue # 還沒遇到目標，靜默跳過

        # 🎯 管線級檢查點：如果最終指標檔已經存在，跳過
        final_metric_file = f"{DIR_PROCESSED}/metrics_{coin_name}.json"
        if os.path.exists(final_metric_file) and not FORCE_OVERWRITE:
            print(f"\n⏭️ [{coin_name}] 已經處理過了，直接跳過整套流程！")
            continue

        print(f"\n{'='*50}\n🚀 處理代幣：{coin_name}\n{'='*50}")

        try:
            if RUN_STEP_1:
                print(f"▶ 執行 Step 1: 抓取 {coin_name} Top 50 名單...")
                step1.run(coin_name, mint_address, DIR_RAW)

            if RUN_STEP_2:
                print(f"▶ 執行 Step 2: 計算 {coin_name} 鏈上核心指標...")
                step2.run(coin_name, DIR_RAW, DIR_PROCESSED, DIR_IMG, DIR_HTML)

            if RUN_STEP_3:
                print(f"▶ 執行 Step 3: 生成 {coin_name} 分析報告...")
                step3.run(coin_name, DIR_PROCESSED, DIR_TXT, DIR_IMG)
                
            if RUN_STEP_4:
                if event_time:
                    print(f"▶ 執行 Step 4: KOL 事件分析...")
                    # 如果 step4 模組有匯入，請確保這裡的呼叫正確
                    # step4.run(coin_name, mint_address, event_time, STEP_4_WINDOW, DIR_RAW, DIR_PROCESSED)
                else:
                    print("⏭️ 跳過 Step 4 (無事件時間資料)")

        except Exception as e:
            # 如果這個幣發生了無可挽回的致命錯誤，印出紅色警告，然後自動換下一個幣！
            print(f"\n❌ 【系統警報】處理 {coin_name} 時發生致命錯誤: {e}")
            print(f"⏭️ 強制跳過 {coin_name}，繼續處理下一個專案...\n")
            continue 

    print("\n🎉 全部執行完畢！")

if __name__ == "__main__":
    main()