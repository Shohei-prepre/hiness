"""MW WP Form アダプター"""
from .base import BaseAdapter


class MWWPFormAdapter(BaseAdapter):
    """WordPress MW WP Form 専用アダプター"""

    def detect(self) -> bool:
        """mw-wp-form クラスが存在するか確認する"""
        return self.page.locator(".mw-wp-form, form.mw-wp-form").count() > 0

    def fill(self) -> bool:
        sender = self.sender
        filled = 0

        if self._try_fill([
            '.mw-wp-form input[name*="name"]:not([name*="kana"]):not([name*="yomi"])',
            '.mw-wp-form input[name="氏名"]',
            '.mw-wp-form input[name="お名前"]',
            '.mw-wp-form input[placeholder*="名前"]:not([placeholder*="ふりがな"])',
            '.mw-wp-form input[placeholder*="お名前"]',
        ], sender["name"]):
            filled += 1

        self._try_fill([
            '.mw-wp-form input[name*="kana"]',
            '.mw-wp-form input[name*="yomi"]',
            '.mw-wp-form input[name*="furigana"]',
            '.mw-wp-form input[name="ふりがな"]',
            '.mw-wp-form input[name="フリガナ"]',
            '.mw-wp-form input[placeholder*="ふりがな"]',
            '.mw-wp-form input[placeholder*="フリガナ"]',
        ], sender["name_kana"])

        self._try_fill([
            '.mw-wp-form input[name*="company"]',
            '.mw-wp-form input[name="会社名"]',
            '.mw-wp-form input[name="企業名"]',
            '.mw-wp-form input[placeholder*="会社"]',
            '.mw-wp-form input[placeholder*="企業"]',
        ], sender["company"])

        self._try_fill([
            '.mw-wp-form input[name*="title"]',
            '.mw-wp-form input[name="役職"]',
            '.mw-wp-form input[placeholder*="役職"]',
        ], sender["title"])

        if self._try_fill([
            '.mw-wp-form input[type="email"]',
            '.mw-wp-form input[name*="email"]',
            '.mw-wp-form input[name*="mail"]',
            '.mw-wp-form input[name="メールアドレス"]',
            '.mw-wp-form input[placeholder*="メール"]',
        ], sender["email"]):
            filled += 1

        self._try_fill([
            '.mw-wp-form input[name*="confirm"]',
            '.mw-wp-form input[name*="email2"]',
            '.mw-wp-form input[name="メールアドレス（確認）"]',
            '.mw-wp-form input[placeholder*="確認"]',
        ], sender["email"])

        self._try_fill([
            '.mw-wp-form input[type="tel"]',
            '.mw-wp-form input[name*="tel"]',
            '.mw-wp-form input[name*="phone"]',
            '.mw-wp-form input[name="電話番号"]',
            '.mw-wp-form input[placeholder*="電話"]',
        ], sender["phone"])

        self._try_select(
            ['.mw-wp-form select[name*="type"]', '.mw-wp-form select[name*="category"]',
             '.mw-wp-form select[name*="subject"]', '.mw-wp-form select[name="お問い合わせ種別"]'],
            ["その他", "ビジネス", "法人", "企業", "サービス", "導入", "other", "Other"],
        )

        if self._try_fill([
            '.mw-wp-form textarea[name*="message"]',
            '.mw-wp-form textarea[name*="content"]',
            '.mw-wp-form textarea[name*="inquiry"]',
            '.mw-wp-form textarea[name="お問い合わせ内容"]',
            '.mw-wp-form textarea[name="メッセージ"]',
            '.mw-wp-form textarea',
        ], self.message):
            filled += 1

        return filled >= 3
