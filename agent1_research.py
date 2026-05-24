"""
エージェント①：リサーチエージェント
会社名 + 公式URL を複数ソースから収集し data/raw_companies.csv に保存する

実行例:
  python agent1_research.py                           # 求人広告代理店（デフォルト）
  python agent1_research.py --industry 不動産仲介
  python agent1_research.py --industry 税理士事務所
"""

import os
import re
import time
import logging
import argparse
from urllib.parse import urljoin, urlparse, quote

import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd
from tqdm import tqdm

from config import (
    HEADERS, REQUEST_TIMEOUT, REQUEST_DELAY, MAX_RETRIES,
    RESEARCH_SOURCES, DATA_DIR, RAW_CSV,
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
            logger.warning(f"  GET失敗({attempt + 1}/{MAX_RETRIES}): {url} - {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(REQUEST_DELAY)
    return None


def extract_root_domain(url: str) -> str:
    """URLからrootドメインを返す"""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_external_url(href: str, own_domains: list[str]) -> bool:
    """外部URLかつ自サイトのドメインでないか確認する"""
    if not href.startswith("http"):
        return False
    domain = extract_root_domain(href)
    return bool(domain) and not any(own in domain for own in own_domains)


# ────────────────────────────────
# 専用ソース（求人広告代理店のみ）
# ────────────────────────────────

def scrape_arna() -> list[dict]:
    """全国求人情報協会のリンクページから会員各社のURLを抽出する"""
    cfg = RESEARCH_SOURCES["arna"]
    if not cfg["enabled"]:
        return []

    url = cfg["link_url"]
    logger.info(f"[ARNA] 開始: {url}")
    results = []

    resp = get(url)
    if not resp:
        logger.error("[ARNA] ページ取得失敗")
        return results

    soup = BeautifulSoup(resp.text, "lxml")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        name = a.get_text(strip=True)

        if not is_external_url(href, ["zenkyukyo.or.jp"]):
            continue
        if not name or len(name) < 2:
            continue
        if any(skip in href for skip in ["facebook", "twitter", "youtube", "instagram"]):
            continue

        results.append({
            "company_name": name,
            "official_url": href.rstrip("/") + "/",
            "source": "ARNA",
        })

    logger.info(f"[ARNA] {len(results)} 件取得")
    return results


def _fetch_jesra_official_url(profile_path: str) -> str:
    """JESRAプロフィールページから会社の公式URLを取得する"""
    url = f"https://www.jesra.or.jp{profile_path}"
    resp = get(url)
    if not resp:
        return ""
    soup = BeautifulSoup(resp.text, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if is_external_url(href, ["jesra.or.jp", "hellowork.mhlw.go.jp"]):
            return href.rstrip("/") + "/"
    return ""


def scrape_jesra_search() -> list[dict]:
    """JESRAの会員企業検索ページ（322社・17ページ）をページネーションして取得する"""
    cfg = RESEARCH_SOURCES["jesra"]
    if not cfg["enabled"]:
        return []

    logger.info("[JESRA] 会員検索ページ スクレイピング開始（322社・17ページ）")
    results = []

    for page in range(1, cfg["max_pages"] + 1):
        url = f"{cfg['search_url']}?key2=0&page={page}&prefcode=0"
        logger.info(f"[JESRA] ページ {page}/{cfg['max_pages']}")

        resp = get(url)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, "lxml")

        name_tags = soup.select(".company-name")
        if not name_tags:
            logger.info(f"[JESRA] ページ {page} でデータなし → 終了")
            break

        profile_links = [
            a["href"] for a in soup.select(".src_btn a[href]")
            if a["href"].startswith("/search/")
        ]

        for i, name_tag in enumerate(name_tags):
            name = name_tag.get_text(strip=True)
            if not name:
                continue

            official_url = ""
            if i < len(profile_links):
                time.sleep(REQUEST_DELAY * 0.5)
                official_url = _fetch_jesra_official_url(profile_links[i])

            results.append({
                "company_name": name,
                "official_url": official_url,
                "source": "JESRA",
            })

        logger.info(f"[JESRA] ページ {page}: {len(name_tags)} 社取得（累計{len(results)}社）")
        time.sleep(REQUEST_DELAY)

    logger.info(f"[JESRA] 合計 {len(results)} 件取得")
    return results


def scrape_jesra_pdf() -> list[dict]:
    """JESRA会員名簿PDF（253社）から会社名だけ抽出する"""
    cfg = RESEARCH_SOURCES["jesra"]
    if not cfg["enabled"]:
        return []

    pdf_url = cfg["pdf_url"]
    logger.info(f"[JESRA-PDF] ダウンロード: {pdf_url}")

    resp = get(pdf_url)
    if not resp:
        logger.error("[JESRA-PDF] PDF取得失敗")
        return []

    tmp_path = os.path.join(DATA_DIR, "_jesra_tmp.pdf")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.write(resp.content)

    results = []
    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    line = line.strip()
                    if not re.search(r"株式会社|有限会社|合同会社|㈱|（株）|LLC|Inc\.|Corp\.", line):
                        continue
                    name = re.sub(r"^\d+[\s\.\)）]+", "", line).strip()
                    name = re.split(r"[\t　]{2,}|\s{3,}", name)[0].strip()
                    name = re.sub(r"[※◆●■▶].*$", "", name).strip()
                    if name and 3 < len(name) < 50:
                        results.append({
                            "company_name": name,
                            "official_url": "",
                            "source": "JESRA-PDF",
                        })
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    logger.info(f"[JESRA-PDF] {len(results)} 件取得")
    return results


def scrape_mynavi_partner() -> list[dict]:
    """マイナビパートナー代理店一覧から会社名とURLを抽出する"""
    cfg = RESEARCH_SOURCES["mynavi_partner"]
    if not cfg["enabled"]:
        return []

    url = cfg["url"]
    logger.info(f"[マイナビ] 開始: {url}")
    results = []

    resp = get(url)
    if not resp:
        logger.error("[マイナビ] ページ取得失敗（JSレンダリングが必要な可能性あり）")
        return results

    soup = BeautifulSoup(resp.text, "lxml")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        name = a.get_text(strip=True)

        if not is_external_url(href, ["mynavi.jp", "mynavi.co.jp"]):
            continue
        if not name or len(name) < 2:
            continue

        results.append({
            "company_name": name,
            "official_url": href.rstrip("/") + "/",
            "source": "マイナビパートナー",
        })

    logger.info(f"[マイナビ] {len(results)} 件取得")
    return results


def scrape_indeed_partner() -> list[dict]:
    """Indeed公認パートナー一覧から会社名とURLを抽出する"""
    cfg = RESEARCH_SOURCES["indeed_partner"]
    if not cfg["enabled"]:
        return []

    url = cfg["url"]
    logger.info(f"[Indeed] 開始: {url}")
    results = []

    resp = get(url)
    if not resp:
        logger.error("[Indeed] ページ取得失敗（JSレンダリングが必要な可能性あり）")
        return results

    soup = BeautifulSoup(resp.text, "lxml")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        name = a.get_text(strip=True)

        if not is_external_url(href, ["indeed.com"]):
            continue
        if not name or len(name) < 2:
            continue

        results.append({
            "company_name": name,
            "official_url": href.rstrip("/") + "/",
            "source": "Indeed公認パートナー",
        })

    logger.info(f"[Indeed] {len(results)} 件取得")
    return results


# ────────────────────────────────
# 汎用ソース（全業界対応）
# ────────────────────────────────

def scrape_prtimes_keyword(industry: str, max_pages: int = 5) -> list[dict]:
    """
    PRtimes のキーワードトピックページから会社名と公式URLを抽出する
    任意の業界キーワードに対応する汎用スクレイパー
    """
    base_url   = "https://prtimes.jp"
    topic_url  = f"https://prtimes.jp/topics/keywords/{quote(industry)}"

    URL_PATTERN = re.compile(
        r"(?:URL|公式サイト|ウェブサイト|ホームページ|HP|公式HP)"
        r"[　 ：:\s]*(https?://[^\s　」\）\)\"\'<>。、]+)",
        re.IGNORECASE,
    )

    logger.info(f"[PRtimes] キーワード「{industry}」で検索開始")
    results = []

    for page in range(1, max_pages + 1):
        list_url = f"{topic_url}/page/{page}/" if page > 1 else topic_url
        logger.info(f"[PRtimes] ページ {page}/{max_pages}: {list_url}")

        resp = get(list_url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        pr_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/main/html/rd/" in href or "/story/" in href:
                full = urljoin(base_url, href)
                if full not in pr_links:
                    pr_links.append(full)

        if not pr_links:
            logger.info(f"[PRtimes] ページ {page} でリリースなし → 終了")
            break

        logger.info(f"[PRtimes] {len(pr_links)} 件のリリースを発見")

        for pr_url in tqdm(pr_links, desc=f"PRtimes p{page}", leave=False):
            time.sleep(REQUEST_DELAY)
            pr_resp = get(pr_url)
            if not pr_resp:
                continue

            pr_soup = BeautifulSoup(pr_resp.text, "lxml")

            company_name = ""
            for sel in [
                ".company-name", ".press-corp-name",
                "[class*='companyName']", "[class*='company_name']",
            ]:
                tag = pr_soup.select_one(sel)
                if tag:
                    company_name = tag.get_text(strip=True)
                    break

            body_text = pr_soup.get_text(" ")
            matches = URL_PATTERN.findall(body_text)

            for found_url in matches:
                found_url = found_url.rstrip("。、．,」）)")
                if found_url and company_name:
                    results.append({
                        "company_name": company_name,
                        "official_url": found_url.rstrip("/") + "/",
                        "source": f"PRtimes/{industry}",
                    })
                    break

        time.sleep(REQUEST_DELAY * 2)

    logger.info(f"[PRtimes] {len(results)} 件取得")
    return results


def scrape_google_search(industry: str, max_pages: int = 5) -> list[dict]:
    """
    Google検索「{industry} 会社 一覧」から会社名と公式URLを抽出する汎用スクレイパー
    ※ Googleのbot対策により取得件数は限られる場合がある
    """
    query   = f"{industry} 会社 一覧"
    results = []

    CORP_PATTERN = re.compile(r"株式会社|有限会社|合同会社|㈱|（株）")

    logger.info(f"[Google] キーワード「{query}」で検索開始")

    for page in range(max_pages):
        start = page * 10
        url   = f"https://www.google.co.jp/search?q={quote(query)}&start={start}&hl=ja"
        resp  = get(url)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, "lxml")

        # 検索結果のタイトルとURLを取得
        for g in soup.select("div.g"):
            title_tag = g.select_one("h3")
            link_tag  = g.select_one("a[href]")
            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text(strip=True)
            href  = link_tag["href"]

            # 会社名らしいタイトル（法人格を含む）
            if not CORP_PATTERN.search(title):
                continue
            if not href.startswith("http"):
                continue
            # Google・Wikipedia等を除外
            if any(x in href for x in ["google.", "wikipedia.", "wikidata.", "facebook.", "twitter."]):
                continue

            # タイトルから会社名を抽出
            name = re.sub(r"[｜|｜\-–—].*$", "", title).strip()
            name = re.sub(r"\s*(公式|会社概要|トップ|ホーム).*$", "", name).strip()

            if name and len(name) >= 4:
                results.append({
                    "company_name": name,
                    "official_url": href.rstrip("/") + "/",
                    "source": f"Google/{industry}",
                })

        logger.info(f"[Google] ページ {page+1}: 累計 {len(results)} 件")
        time.sleep(REQUEST_DELAY * 3)  # Googleへの負荷軽減

    logger.info(f"[Google] {len(results)} 件取得")
    return results


# ────────────────────────────────
# 重複排除・メイン処理
# ────────────────────────────────

def deduplicate(records: list[dict]) -> list[dict]:
    """rootドメインが同じものを重複とみなし先着1件だけ残す"""
    seen_domains: set[str] = set()
    unique: list[dict] = []

    for rec in records:
        url = rec["official_url"]
        if not url:
            unique.append(rec)
            continue
        domain = extract_root_domain(url)
        if domain and domain not in seen_domains:
            seen_domains.add(domain)
            unique.append(rec)

    return unique


def run(industry: str = "求人広告代理店") -> None:
    """
    全ソースを業界に応じて切り替えて実行し、raw_companies.csv に保存する

    求人広告代理店: 専用ソース（ARNA/JESRA/マイナビ/Indeed）+ PRtimes
    その他の業界:   PRtimes キーワード検索 + Google 検索
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    all_records: list[dict] = []

    RECRUITMENT_INDUSTRY = "求人広告代理店"

    if industry == RECRUITMENT_INDUSTRY:
        # 専用スクレイパーを使用
        logger.info(f"[リサーチ] 業界: {industry}（専用ソース使用）")
        scrapers = [
            scrape_arna,
            scrape_jesra_search,
            scrape_jesra_pdf,
            lambda: scrape_prtimes_keyword("人材紹介会社"),
            scrape_mynavi_partner,
            scrape_indeed_partner,
        ]
    else:
        # 汎用スクレイパーを使用
        logger.info(f"[リサーチ] 業界: {industry}（汎用ソース使用）")
        scrapers = [
            lambda: scrape_prtimes_keyword(industry),
            lambda: scrape_google_search(industry),
        ]

    for scraper in scrapers:
        try:
            records = scraper()
            all_records.extend(records)
            logger.info(f"  -> 累計: {len(all_records)} 件")
        except Exception as e:
            logger.error(f"スクレイパーエラー [{scraper.__name__}]: {e}")
        time.sleep(REQUEST_DELAY)

    unique_records = deduplicate(all_records)

    logger.info(
        f"重複排除: {len(all_records)} 件 -> {len(unique_records)} 件"
    )

    df = pd.DataFrame(unique_records, columns=["company_name", "official_url", "source"])
    df.to_csv(RAW_CSV, index=False, encoding="utf-8-sig")

    print(f"\n[完了] リサーチ完了: {len(unique_records)} 社 -> {RAW_CSV}")
    print(f"  URLあり : {sum(1 for r in unique_records if r['official_url'])} 社")
    print(f"  URLなし : {sum(1 for r in unique_records if not r['official_url'])} 社")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="会社リストをリサーチして raw_companies.csv に保存する")
    parser.add_argument(
        "--industry",
        default="求人広告代理店",
        help="対象業界名（例: 不動産仲介, 税理士事務所, ITコンサル）。デフォルト: 求人広告代理店",
    )
    args = parser.parse_args()
    run(args.industry)
