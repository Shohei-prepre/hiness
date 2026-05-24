"""
エージェント①：リサーチエージェント
求人広告代理店の「会社名 + 公式URL」を複数ソースから収集し
data/raw_companies.csv に保存する

実行: python agent1_research.py
"""

import os
import re
import time
import logging
from urllib.parse import urljoin, urlparse

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
    """URLからrootドメインを返す（例: https://foo.co.jp/bar → foo.co.jp）"""
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
# ソース① 全国求人情報協会（ARNA）
# ────────────────────────────────

def scrape_arna() -> list[dict]:
    """
    全国求人情報協会のリンクページから会員各社のURLを抽出する
    https://www.zenkyukyo.or.jp/link/ に会員社へのリンクが掲載されている
    """
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
        # ナビゲーション等の無関係リンクを除外
        if any(skip in href for skip in ["facebook", "twitter", "youtube", "instagram"]):
            continue

        results.append({
            "company_name": name,
            "official_url": href.rstrip("/") + "/",
            "source": "ARNA",
        })

    logger.info(f"[ARNA] {len(results)} 件取得")
    return results


# ────────────────────────────────
# ソース② 日本人材紹介事業協会（JESRA）
# ────────────────────────────────

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
    """
    JESRAの会員企業検索ページ（322社・17ページ）をページネーションし
    各社のプロフィールページから公式URLを取得する
    https://www.jesra.or.jp/search/?key2=0&page=N&prefcode=0
    """
    cfg = RESEARCH_SOURCES["jesra"]
    if not cfg["enabled"]:
        return []

    logger.info("[JESRA] 会員検索ページ スクレイピング開始（322社・17ページ）")
    results = []
    base = "https://www.jesra.or.jp"

    for page in range(1, cfg["max_pages"] + 1):
        url = f"{cfg['search_url']}?key2=0&page={page}&prefcode=0"
        logger.info(f"[JESRA] ページ {page}/{cfg['max_pages']}")

        resp = get(url)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, "lxml")

        # 会社名を取得
        name_tags = soup.select(".company-name")
        if not name_tags:
            logger.info(f"[JESRA] ページ {page} でデータなし → 終了")
            break

        # 各カードのプロフィールリンク（/search/XXXX/）を取得
        profile_links = [
            a["href"] for a in soup.select(".src_btn a[href]")
            if a["href"].startswith("/search/")
        ]

        for i, name_tag in enumerate(name_tags):
            name = name_tag.get_text(strip=True)
            if not name:
                continue

            # プロフィールページから公式URLを取得
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
    """
    JESRA会員名簿PDF（253社）から会社名だけ抽出する
    URLはないため official_url は空欄 → agent2でURL発見を試みる
    """
    cfg = RESEARCH_SOURCES["jesra"]
    if not cfg["enabled"]:
        return []

    pdf_url = cfg["pdf_url"]
    logger.info(f"[JESRA-PDF] ダウンロード: {pdf_url}")

    resp = get(pdf_url)
    if not resp:
        logger.error("[JESRA-PDF] PDF取得失敗")
        return []

    # 一時ファイルに保存してpdfplumberで読み込む
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
                    # 会社名の判定：法人格キーワードを含む行
                    if not re.search(r"株式会社|有限会社|合同会社|㈱|（株）|LLC|Inc\.|Corp\.", line):
                        continue
                    # 行頭の番号・記号を除去
                    name = re.sub(r"^\d+[\s\.\)）]+", "", line).strip()
                    # タブや空白以降（電話番号・住所等）を除去
                    name = re.split(r"[\t　]{2,}|\s{3,}", name)[0].strip()
                    # 余分な記号を除去
                    name = re.sub(r"[※◆●■▶].*$", "", name).strip()
                    if name and 3 < len(name) < 50:
                        results.append({
                            "company_name": name,
                            "official_url": "",   # agent2で発見する
                            "source": "JESRA-PDF",
                        })
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    logger.info(f"[JESRA-PDF] {len(results)} 件取得")
    return results


# ────────────────────────────────
# ソース③ PRtimes（人材紹介キーワード）
# ────────────────────────────────

def scrape_prtimes() -> list[dict]:
    """
    PRtimes の人材紹介会社キーワードページから
    プレスリリース本文の「URL：https://xxx」パターンで公式URLを抽出する
    """
    cfg = RESEARCH_SOURCES["prtimes"]
    if not cfg["enabled"]:
        return []

    logger.info("[PRtimes] 開始（人材紹介会社キーワード）")

    # 「URL：https://xxx」「公式サイト：https://xxx」パターン
    URL_PATTERN = re.compile(
        r"(?:URL|公式サイト|ウェブサイト|ホームページ|HP|公式HP)"
        r"[　 ：:\s]*(https?://[^\s　」\）\)\"\'<>。、]+)",
        re.IGNORECASE,
    )

    results = []
    base_url = cfg["base_url"]
    topic_url = cfg["topic_url"]

    for page in range(1, cfg["max_pages"] + 1):
        # PRtimesのページネーション形式: /page/N/ または ?page=N どちらも試みる
        list_url = f"{topic_url}/page/{page}/" if page > 1 else topic_url
        logger.info(f"[PRtimes] トピックページ {page}/{cfg['max_pages']}: {list_url}")

        resp = get(list_url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # プレスリリース個別ページへのリンクを収集
        pr_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # PRtimesのリリースURLは /main/html/rd/ を含む
            if "/main/html/rd/" in href or "/story/" in href:
                full = urljoin(base_url, href)
                if full not in pr_links:
                    pr_links.append(full)

        logger.info(f"[PRtimes] {len(pr_links)} 件のリリースを発見")
        if not pr_links:
            logger.info(f"[PRtimes] ページ {page} でリリースなし → 終了")
            break

        for pr_url in tqdm(pr_links, desc=f"PRtimes p{page}", leave=False):
            time.sleep(REQUEST_DELAY)
            pr_resp = get(pr_url)
            if not pr_resp:
                continue

            pr_soup = BeautifulSoup(pr_resp.text, "lxml")

            # 発信元会社名を複数セレクタで試みる
            company_name = ""
            for sel in [
                ".company-name",
                ".press-corp-name",
                "[class*='companyName']",
                "[class*='company_name']",
                "h2.company",
            ]:
                tag = pr_soup.select_one(sel)
                if tag:
                    company_name = tag.get_text(strip=True)
                    break

            # 本文テキストからURLパターンを抽出（1リリース1URLのみ）
            body_text = pr_soup.get_text(" ")
            matches = URL_PATTERN.findall(body_text)

            for found_url in matches:
                found_url = found_url.rstrip("。、．,」）)")
                if found_url and company_name:
                    results.append({
                        "company_name": company_name,
                        "official_url": found_url.rstrip("/") + "/",
                        "source": "PRtimes",
                    })
                    break

        time.sleep(REQUEST_DELAY * 2)

    logger.info(f"[PRtimes] {len(results)} 件取得")
    return results


# ────────────────────────────────
# ソース④ マイナビパートナー
# ────────────────────────────────

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


# ────────────────────────────────
# ソース⑤ Indeed公認パートナー
# ────────────────────────────────

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
# 重複排除・メイン処理
# ────────────────────────────────

def deduplicate(records: list[dict]) -> list[dict]:
    """rootドメインが同じものを重複とみなし先着1件だけ残す。URL空欄は別途保持"""
    seen_domains: set[str] = set()
    unique: list[dict] = []

    for rec in records:
        url = rec["official_url"]
        if not url:
            # URLなし（JESRA-PDF）はそのまま追加（agent2でURL発見）
            unique.append(rec)
            continue
        domain = extract_root_domain(url)
        if domain and domain not in seen_domains:
            seen_domains.add(domain)
            unique.append(rec)

    return unique


def run() -> None:
    """全ソースを順番に実行し、raw_companies.csv に保存する"""
    os.makedirs(DATA_DIR, exist_ok=True)

    all_records: list[dict] = []

    scrapers = [
        scrape_arna,
        scrape_jesra_search,
        scrape_jesra_pdf,
        scrape_prtimes,
        scrape_mynavi_partner,
        scrape_indeed_partner,
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
    print(f"  URLなし : {sum(1 for r in unique_records if not r['official_url'])} 社 (JESRA-PDF)")


if __name__ == "__main__":
    run()
