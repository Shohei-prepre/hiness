"""
エージェント②：リッチ化エージェント
raw_companies.csv の公式URLから問い合わせフォームURLを発見し
data/enriched_companies.csv に保存する

実行: python agent2_enrich.py
"""

import os
import time
import logging
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm

from config import (
    HEADERS, REQUEST_TIMEOUT, REQUEST_DELAY, MAX_RETRIES,
    FORM_PATHS, EXCLUDED_PLATFORM_DOMAINS, EXCLUDED_FORM_PATHS,
    DATA_DIR, RAW_CSV, ENRICHED_CSV,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ────────────────────────────────
# 共通ユーティリティ
# ────────────────────────────────

def get(url: str) -> requests.Response | None:
    """GETリクエストを送信する。失敗時はNoneを返す"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(REQUEST_DELAY * 0.5)
    return None


def root_domain(url: str) -> str:
    """URLからrootドメインを返す"""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


# ────────────────────────────────
# フォームページ判定
# ────────────────────────────────

def has_contact_form(soup: BeautifulSoup) -> bool:
    """
    ページにお問い合わせフォームが存在するか確認する
    <form> + (<textarea> or <input type=text|email|tel>) の組み合わせで判定
    """
    forms = soup.find_all("form")
    if not forms:
        return False

    for form in forms:
        has_textarea = form.find("textarea") is not None
        has_text_input = form.find(
            "input",
            attrs={"type": lambda t: t in ("text", "email", "tel") if t else True},
        ) is not None
        if has_textarea or has_text_input:
            return True

    return False


def is_excluded_path(url: str) -> bool:
    """採用・サポートなど用途違いURLを除外する"""
    path = urlparse(url).path.lower()
    return any(ex in path for ex in EXCLUDED_FORM_PATHS)


def is_third_party_platform(url: str) -> bool:
    """第三者フォームプラットフォームのURLを除外する"""
    domain = root_domain(url)
    return any(ex in domain for ex in EXCLUDED_PLATFORM_DOMAINS)


# ────────────────────────────────
# 安全チェック
# ────────────────────────────────

def safety_check(
    company_name: str,
    official_url: str,
    form_url: str,
    soup: BeautifulSoup,
) -> tuple[bool, str]:
    """
    フォームURLの安全性を確認する
    returns: (ok, reason)
    """
    # ① rootドメインが一致するか
    if root_domain(official_url) != root_domain(form_url):
        return False, f"ドメイン不一致: {root_domain(official_url)} vs {root_domain(form_url)}"

    # ② 第三者プラットフォームでないか
    if is_third_party_platform(form_url):
        return False, f"第三者プラットフォーム: {root_domain(form_url)}"

    # ③ 用途違いURLでないか
    if is_excluded_path(form_url):
        return False, f"用途違いURL: {form_url}"

    # ④ 会社名がページHTML内に含まれるか（法人格を除いた短縮名で確認）
    # 「株式会社」「有限会社」等を除いた部分で判定
    import re
    short_name = re.sub(r"株式会社|有限会社|合同会社|一般社団法人|㈱|（株）|\s", "", company_name)
    short_name = short_name[:8]  # 前半8文字で判定
    if short_name and len(short_name) >= 3:
        page_text = soup.get_text()
        if short_name not in page_text:
            return False, f"会社名未検出: {short_name}"

    return True, "OK"


# ────────────────────────────────
# フォームURL発見ロジック
# ────────────────────────────────

def find_form_url(official_url: str, company_name: str) -> tuple[str, str]:
    """
    公式URLからお問い合わせフォームURLを発見する
    returns: (form_url, status)
      status: "found" | "not_found" | "skip"
    """
    if not official_url:
        return "", "skip"

    base = official_url.rstrip("/")
    domain = root_domain(official_url)

    # まず公式URLトップページを取得して、フォームリンクを探す
    top_resp = get(official_url)
    if top_resp:
        top_soup = BeautifulSoup(top_resp.text, "lxml")

        # トップページ内のリンクからフォームらしいものを探す
        for a in top_soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)

            # リンクテキストでフォームらしいものを判定
            if any(kw in text for kw in ["お問い合わせ", "問い合わせ", "contact", "Contact", "inquiry", "Inquiry"]):
                candidate = urljoin(official_url, href)
                # 同一ドメインかつ除外パスでないか
                if root_domain(candidate) == domain and not is_excluded_path(candidate):
                    cand_resp = get(candidate)
                    if cand_resp:
                        cand_soup = BeautifulSoup(cand_resp.text, "lxml")
                        if has_contact_form(cand_soup):
                            ok, reason = safety_check(company_name, official_url, candidate, cand_soup)
                            if ok:
                                return candidate, "found"

    # パスを総当たりで試みる
    for path in FORM_PATHS:
        candidate = base + path
        time.sleep(REQUEST_DELAY * 0.3)

        resp = get(candidate)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        if not has_contact_form(soup):
            continue

        ok, reason = safety_check(company_name, official_url, candidate, soup)
        if ok:
            return candidate, "found"

    return "", "not_found"


# ────────────────────────────────
# メイン処理
# ────────────────────────────────

def run() -> None:
    """raw_companies.csv を読み込んでフォームURLを発見し enriched_companies.csv に保存する"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(RAW_CSV):
        print(f"[ERROR] 入力ファイルが見つかりません: {RAW_CSV}")
        print("  先に agent1_research.py を実行してください")
        return

    df = pd.read_csv(RAW_CSV, encoding="utf-8-sig", dtype=str).fillna("")
    logger.info(f"読み込み: {len(df)} 社 <- {RAW_CSV}")

    # URLなし（JESRA-PDF）の行はスキップ
    total      = len(df)
    skip_count = (df["official_url"] == "").sum()
    target_df  = df[df["official_url"] != ""].copy()
    logger.info(f"URLあり: {len(target_df)} 社 / URLなし（スキップ）: {skip_count} 社")

    results = []

    for _, row in tqdm(target_df.iterrows(), total=len(target_df), desc="フォーム発見"):
        company_name = row["company_name"]
        official_url = row["official_url"]

        time.sleep(REQUEST_DELAY * 0.5)

        form_url, status = find_form_url(official_url, company_name)

        results.append({
            "company_name": company_name,
            "official_url": official_url,
            "form_url":     form_url,
            "status":       status,
            "source":       row.get("source", ""),
        })

    # URLなし行も保持（statusはskip）
    skip_rows = df[df["official_url"] == ""].copy()
    skip_rows["form_url"] = ""
    skip_rows["status"]   = "skip"

    result_df = pd.concat([pd.DataFrame(results), skip_rows], ignore_index=True)
    result_df.to_csv(ENRICHED_CSV, index=False, encoding="utf-8-sig")

    found_count = sum(1 for r in results if r["status"] == "found")
    logger.info(f"フォーム発見: {found_count} / {len(target_df)} 社")

    print(f"\n[完了] リッチ化完了 -> {ENRICHED_CSV}")
    print(f"  フォームURL発見: {found_count} 社")
    print(f"  フォームなし   : {len(target_df) - found_count} 社")
    print(f"  URLなしスキップ: {skip_count} 社")
    print(f"  合計           : {total} 社")


if __name__ == "__main__":
    run()
