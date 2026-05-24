"""
設定ファイル - 自社情報とシステム設定を一元管理する
送信前に SENDER_INFO と MESSAGE_TEMPLATE を実際の値で埋めること
"""

# ────────────────────────────────
# 自社情報（後で実際の値に置き換える）
# ────────────────────────────────
SENDER_INFO = {
    "company":   "{{YOUR_COMPANY_NAME}}",
    "name":      "{{YOUR_NAME}}",
    "name_kana": "{{YOUR_NAME_KANA}}",   # ふりがな（ひらがな）
    "email":     "{{YOUR_EMAIL}}",
    "phone":     "{{YOUR_PHONE}}",
    "title":     "{{YOUR_TITLE}}",
    "url":       "{{YOUR_COMPANY_URL}}",
}

# ────────────────────────────────
# 営業メッセージ本文（後で記入）
# ────────────────────────────────
MESSAGE_TEMPLATE = """\
{{MESSAGE_BODY}}
"""

# ────────────────────────────────
# HTTPリクエスト設定
# ────────────────────────────────
REQUEST_TIMEOUT = 10    # 秒
REQUEST_DELAY   = 1.5   # リクエスト間隔（サーバー負荷軽減）
MAX_RETRIES     = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

# ────────────────────────────────
# ① リサーチ対象ソース（求人広告代理店）
# ────────────────────────────────
RESEARCH_SOURCES = {
    "arna": {
        "enabled":  True,
        "name":     "全国求人情報協会（ARNA）",
        # リンクページに会員各社へのURLが掲載されている
        "link_url": "https://www.zenkyukyo.or.jp/link/",
    },
    "jesra": {
        "enabled":   True,
        "name":      "日本人材紹介事業協会（JESRA）",
        # 会員企業検索ページ（ページネーションあり）
        "search_url": "https://www.jesra.or.jp/search/",
        # 会員名簿PDF（253社・社名のみ → agent2でURL検索）
        "pdf_url":    "https://jesra.or.jp/pdf/johokokai/2024/kaiinmeibo_20240612.pdf",
        "max_pages":  20,
    },
    "prtimes": {
        "enabled":   True,
        "name":      "PRtimes（人材紹介キーワード）",
        "base_url":  "https://prtimes.jp",
        # 正しいキーワードトピックURL
        "topic_url": "https://prtimes.jp/topics/keywords/人材紹介会社",
        "max_pages": 5,
    },
    "mynavi_partner": {
        "enabled": True,
        "name":    "マイナビパートナー代理店",
        "url":     "https://partner.mynavi.jp/partner/list/",
    },
    "indeed_partner": {
        "enabled": True,
        "name":    "Indeed公認パートナー",
        "url":     "https://jp.indeed.com/hire/ats-partners",
    },
}

# ────────────────────────────────
# ② フォーム発見パス（順番に試す）
# ────────────────────────────────
FORM_PATHS = [
    "/contact/",
    "/contact",
    "/inquiry/",
    "/inquiry",
    "/contact-us/",
    "/contact-us",
    "/お問い合わせ/",
    "/お問い合わせ",
    "/form/",
    "/form",
    "/toiawase/",
    "/toiawase",
]

# ────────────────────────────────
# 除外：第三者フォームプラットフォームのドメイン
# ────────────────────────────────
EXCLUDED_PLATFORM_DOMAINS = [
    "form-mailer.jp",
    "formrun.me",
    "tayori.com",
    "kintoneapp.com",
    "form.io",
    "typeform.com",
    "forms.gle",
    "google.com",
    "mailchimp.com",
]

# ────────────────────────────────
# 除外：用途違いURLパス（採用・サポート・IRなど）
# ────────────────────────────────
EXCLUDED_FORM_PATHS = [
    "/recruit",
    "/careers",
    "/support",
    "/press",
    "/ir/",
    "/news",
    "/blog",
    "/media",
]

# ────────────────────────────────
# データファイルパス
# ────────────────────────────────
DATA_DIR          = "data"
RAW_CSV           = f"{DATA_DIR}/raw_companies.csv"
ENRICHED_CSV      = f"{DATA_DIR}/enriched_companies.csv"
DRYRUN_RESULT_CSV = f"{DATA_DIR}/dryrun_results.csv"
SAFE_CSV          = f"{DATA_DIR}/safe.csv"
SENT_LOG_CSV      = f"{DATA_DIR}/sent_log.csv"
