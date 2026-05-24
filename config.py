"""
設定ファイル - 自社情報とシステム設定を一元管理する
送信前に SENDER_INFO と MESSAGE_TEMPLATE を実際の値で埋めること
"""

# ────────────────────────────────
# 自社情報
# GitHub Actions では Secrets から自動注入される
# ローカル実行時は直接ここに記入する
# ────────────────────────────────
import os

SENDER_INFO = {
    "company":   os.getenv("SENDER_COMPANY",   "{{YOUR_COMPANY_NAME}}"),
    "name":      os.getenv("SENDER_NAME",      "{{YOUR_NAME}}"),
    "name_kana": os.getenv("SENDER_NAME_KANA", "{{YOUR_NAME_KANA}}"),
    "email":     os.getenv("SENDER_EMAIL",     "{{YOUR_EMAIL}}"),
    "phone":     os.getenv("SENDER_PHONE",     "{{YOUR_PHONE}}"),
    "title":     os.getenv("SENDER_TITLE",     "{{YOUR_TITLE}}"),
    "url":       os.getenv("SENDER_URL",       "{{YOUR_COMPANY_URL}}"),
}

# ────────────────────────────────
# 営業メッセージ テンプレート（3部構成）
# OPENING / CLOSING は固定、BODY は Gemini が会社ごとに生成する
# ────────────────────────────────

MESSAGE_OPENING = """\
突然のご連絡、失礼いたします。
{company}の{name}と申します。

{target_company}様のご事業について拝見し、
ぜひ一度ご提案させていただきたくご連絡差し上げました。\
"""

# ─ ここだけ Gemini が会社ごとに生成する ─
# Geminiへの指示プロンプト（agent_personalize.py が使用）
GEMINI_PROMPT_TEMPLATE = """\
あなたはBtoB営業のプロフェッショナルです。
以下の情報をもとに、営業メッセージの「本文中盤部分」だけを生成してください。

【送り手の情報】
会社名：{sender_company}
サービス：営業代行（新規アポ獲得・商談代行）
提供価値：クライアントの新規開拓コストを下げ、アポ数と受注率を上げる

【送り先の情報】
会社名：{target_company}
業界：{industry}
公式サイトから読み取った情報：
{company_summary}

【生成ルール】
- 200文字以内
- 「{target_company}様は〜」という書き出しで始める
- 相手の事業・強みに言及してから課題感・提案につなげる
- 押しつけがましくせず、興味を持ってもらえる一文で終わる
- 挨拶・署名は不要（前後に固定文が入るため）
- 敬語・丁寧語で統一する\
"""

# ─ Gemini生成の後に続く固定ブロック ─
MESSAGE_VALUE = """\
弊社はまだ立ち上げ段階のため、固定費ゼロの完全成果報酬でご支援しております。
実績こそ多くはございませんが、だからこそ「貴社にメリットがある形でなければ報酬をいただかない」
という強いコミットメントでご支援できると考えております。\
"""

MESSAGE_CLOSING = """\
まずは30分、オンラインでお話しさせていただけますでしょうか。
ご都合のよい日時をお聞かせいただければ幸いです。

何卒よろしくお願いいたします。

───────────────────────
{name}（{title}）
{company}
Mail : {email}
Tel  : {phone}
URL  : {url}
───────────────────────\
"""

# 後方互換：旧 MESSAGE_TEMPLATE（環境変数での上書きも可）
MESSAGE_TEMPLATE = os.getenv("SENDER_MESSAGE_BODY", "")

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
