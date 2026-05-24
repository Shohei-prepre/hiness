"""
STEP2.5: Gemini API で各社向けのパーソナライズ本文を生成する
enriched_companies.csv を読み込み、フォームURLが見つかった企業についてのみ
会社サマリーを生成してキャッシュする
"""
import os
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

from config import (
    GEMINI_PROMPT_TEMPLATE,
    SENDER_INFO,
    ENRICHED_CSV,
    HEADERS,
    REQUEST_TIMEOUT,
    REQUEST_DELAY,
)

# ── Gemini 設定 ──────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")   # ← ここにAPIキーを設定するか環境変数へ
PERSONALIZED_CSV = "data/personalized.csv"

# 1社あたりのサイト要約に使う文字数上限
SUMMARY_MAX_CHARS = 1000


def scrape_company_summary(url: str) -> str:
    """公式サイトのトップページからテキストを抽出してサマリーとして返す"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        # scriptやstyleを除去して本文テキストを取得
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:SUMMARY_MAX_CHARS]
    except Exception as e:
        return f"（サイト取得失敗: {e}）"


def generate_personalized_body(company_name: str, industry: str, company_summary: str, model) -> str:
    """Gemini APIで1社分のパーソナライズ本文（中盤）を生成する"""
    prompt = GEMINI_PROMPT_TEMPLATE.format(
        sender_company=SENDER_INFO["company"],
        target_company=company_name,
        industry=industry,
        company_summary=company_summary,
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"  [Gemini失敗] {company_name}: {e}")
        return ""


def run(industry: str = "求人広告代理店"):
    """
    メイン処理：enriched_companies.csv → personalized.csv
    フォームURLが見つかっている企業のみ対象
    """
    if not GEMINI_API_KEY:
        print("[エラー] GEMINI_API_KEY が設定されていません。")
        print("  config.py の GEMINI_API_KEY に設定するか、環境変数 GEMINI_API_KEY を設定してください。")
        return

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # 入力CSVを読み込む
    try:
        df = pd.read_csv(ENRICHED_CSV, encoding="utf-8-sig")
    except FileNotFoundError:
        print(f"[エラー] {ENRICHED_CSV} が見つかりません。先にSTEP2を実行してください。")
        return

    # フォームが見つかった企業のみ処理
    targets = df[df["status"] == "found"].copy()
    print(f"[開始] パーソナライズ対象: {len(targets)}社")

    # すでに処理済みのCSVがあれば読み込んでスキップ判定
    done_companies: set = set()
    if os.path.exists(PERSONALIZED_CSV):
        done_df = pd.read_csv(PERSONALIZED_CSV, encoding="utf-8-sig")
        done_companies = set(done_df["company_name"].tolist())
        print(f"  既処理: {len(done_companies)}社 → スキップ")

    results = []
    for i, row in targets.iterrows():
        company_name = row["company_name"]
        official_url = row.get("official_url", "")
        form_url     = row.get("form_url", "")

        if company_name in done_companies:
            continue

        print(f"  [{i+1}/{len(targets)}] {company_name} ...", end=" ", flush=True)

        # 公式サイトからサマリー取得
        summary = scrape_company_summary(official_url) if official_url else ""

        # Geminiで本文生成
        body = generate_personalized_body(company_name, industry, summary, model)

        results.append({
            "company_name":      company_name,
            "official_url":      official_url,
            "form_url":          form_url,
            "industry":          industry,
            "company_summary":   summary,
            "personalized_body": body,
        })
        print("完了" if body else "空（フォールバックを使用）")

        time.sleep(REQUEST_DELAY)

    if not results:
        print("[情報] 新規処理対象がありませんでした。")
        return

    # 既存CSVに追記
    new_df = pd.DataFrame(results)
    if os.path.exists(PERSONALIZED_CSV):
        existing = pd.read_csv(PERSONALIZED_CSV, encoding="utf-8-sig")
        new_df = pd.concat([existing, new_df], ignore_index=True)

    new_df.to_csv(PERSONALIZED_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[完了] {PERSONALIZED_CSV} に {len(results)}社分を保存しました。")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gemini APIで営業メッセージをパーソナライズする")
    parser.add_argument("--industry", default="求人広告代理店", help="対象業界名（デフォルト: 求人広告代理店）")
    args = parser.parse_args()
    run(args.industry)
