"""
STEP4: 実際のフォーム送信
dryrun_results.csv の fill_ok=True 企業にのみ送信する
送信記録を sent_log.csv に保存する
"""
import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright

from config import REQUEST_DELAY, DRYRUN_RESULT_CSV, SENT_LOG_CSV
from agent3_dryrun import process_one

PERSONALIZED_CSV = "data/personalized.csv"


def run():
    """
    メイン処理：dryrun_results.csv + personalized.csv → sent_log.csv
    ドライランで fill_ok=True だった企業にのみ実際に送信する
    """
    # ドライラン結果の読み込み
    try:
        dryrun_df = pd.read_csv(DRYRUN_RESULT_CSV, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"[エラー] {DRYRUN_RESULT_CSV} が見つかりません。先にSTEP3を実行してください。")
        return

    # パーソナライズデータの読み込み
    try:
        pers_df = pd.read_csv(PERSONALIZED_CSV, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"[エラー] {PERSONALIZED_CSV} が見つかりません。先にSTEP2.5を実行してください。")
        return

    # fill_ok=True の企業のみ対象
    ok_companies = set(dryrun_df[dryrun_df["fill_ok"] == True]["company_name"].tolist())

    # すでに送信済みの企業をスキップ
    sent_companies: set = set()
    if os.path.exists(SENT_LOG_CSV):
        sent_df = pd.read_csv(SENT_LOG_CSV, encoding="utf-8-sig")
        sent_companies = set(sent_df["company_name"].tolist())
        print(f"  既送信: {len(sent_companies)}社 → スキップ")

    targets = pers_df[
        pers_df["company_name"].isin(ok_companies) &
        ~pers_df["company_name"].isin(sent_companies)
    ].copy()

    if targets.empty:
        print("[情報] 送信対象がありません。")
        return

    print(f"[開始] 実際に送信する企業数: {len(targets)}社")
    print("  !! 本当に送信します。Ctrl+C でキャンセルしてください（5秒後に開始） !!")
    time.sleep(5)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="ja-JP",
        )
        page = context.new_page()

        for i, row in targets.iterrows():
            company = row["company_name"]
            print(f"  [{i+1}/{len(targets)}] {company} ...", end=" ", flush=True)

            # dry_run=False で実際に送信
            res = process_one(page, row.to_dict(), dry_run=False)
            res["sent"] = res["submit_ok"]
            results.append(res)

            status = "送信完了" if res["submit_ok"] else f"送信失敗 ({res['error']})"
            print(status)

            time.sleep(REQUEST_DELAY * 2)   # 送信後は少し長めに待機

        browser.close()

    # 送信ログに追記
    new_log_df = pd.DataFrame(results)
    if os.path.exists(SENT_LOG_CSV):
        existing = pd.read_csv(SENT_LOG_CSV, encoding="utf-8-sig")
        new_log_df = pd.concat([existing, new_log_df], ignore_index=True)

    new_log_df.to_csv(SENT_LOG_CSV, index=False, encoding="utf-8-sig")

    sent_count = sum(r["submit_ok"] for r in results)
    print(f"\n[完了] 送信: {sent_count}/{len(results)}社 → {SENT_LOG_CSV}")


if __name__ == "__main__":
    run()
