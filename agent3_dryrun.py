"""
STEP3: Playwright ドライラン
personalized.csv のフォームURLに対して自動入力のみ行い、送信はしない
結果を dryrun_results.csv に保存する
"""
import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from config import REQUEST_DELAY, DRYRUN_RESULT_CSV
from adapters import get_adapter

PERSONALIZED_CSV = "data/personalized.csv"
PAGE_TIMEOUT = 20_000   # ms


def process_one(page, row: dict, dry_run: bool = True) -> dict:
    """1社分のフォームに入力を試みて結果を返す"""
    company_name      = row["company_name"]
    form_url          = row["form_url"]
    personalized_body = row.get("personalized_body", "")

    result = {
        "company_name": company_name,
        "form_url":     form_url,
        "adapter":      "",
        "fill_ok":      False,
        "submit_ok":    False,
        "error":        "",
    }

    try:
        page.goto(form_url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)   # JS描画待ち

        adapter = get_adapter(page, company_name, personalized_body, dry_run=dry_run)
        result["adapter"] = type(adapter).__name__

        result["fill_ok"] = adapter.fill()

        if result["fill_ok"]:
            result["submit_ok"] = adapter.submit()

    except PlaywrightTimeout:
        result["error"] = "タイムアウト"
    except Exception as e:
        result["error"] = str(e)[:200]

    return result


def run(dry_run: bool = True):
    """
    メイン処理：personalized.csv → dryrun_results.csv
    dry_run=True  の場合、フォーム送信ボタンをクリックしない
    dry_run=False の場合、agent4_submit.py から呼び出される（実際に送信）
    """
    try:
        df = pd.read_csv(PERSONALIZED_CSV, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"[エラー] {PERSONALIZED_CSV} が見つかりません。先にSTEP2.5を実行してください。")
        return

    targets = df.copy()
    print(f"[開始] ドライラン対象: {len(targets)}社 (dry_run={dry_run})")

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

            res = process_one(page, row.to_dict(), dry_run=dry_run)
            results.append(res)

            status = "OK" if res["fill_ok"] else f"失敗 ({res['error'] or 'フィールド不足'})"
            print(f"{res['adapter']} / {status}")

            time.sleep(REQUEST_DELAY)

        browser.close()

    result_df = pd.DataFrame(results)
    result_df.to_csv(DRYRUN_RESULT_CSV, index=False, encoding="utf-8-sig")

    ok_count = result_df["fill_ok"].sum()
    print(f"\n[完了] 成功: {ok_count}/{len(results)}社 → {DRYRUN_RESULT_CSV}")


if __name__ == "__main__":
    run(dry_run=True)
