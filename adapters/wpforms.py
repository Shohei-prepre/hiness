"""WPForms アダプター"""
from .base import BaseAdapter


class WPFormsAdapter(BaseAdapter):
    """WordPress WPForms 専用アダプター"""

    def detect(self) -> bool:
        """wpforms クラスが存在するか確認する"""
        return self.page.locator(".wpforms-form, form.wpforms-form, #wpforms-form").count() > 0

    def fill(self) -> bool:
        sender = self.sender
        filled = 0

        if self._try_fill([
            '.wpforms-form input[name*="name"]:not([name*="last"]):not([name*="kana"])',
            '.wpforms-form input[id*="name"]:not([id*="last"])',
            '.wpforms-form input[placeholder*="名前"]:not([placeholder*="姓"])',
            '.wpforms-form input[placeholder*="お名前"]',
        ], sender["name"]):
            filled += 1

        # 姓（last name）フィールド対応
        self._try_fill([
            '.wpforms-form input[name*="last"]',
            '.wpforms-form input[id*="last"]',
        ], sender["name"])

        self._try_fill([
            '.wpforms-form input[name*="kana"]',
            '.wpforms-form input[name*="yomi"]',
            '.wpforms-form input[name*="furigana"]',
            '.wpforms-form input[placeholder*="ふりがな"]',
            '.wpforms-form input[placeholder*="フリガナ"]',
        ], sender["name_kana"])

        self._try_fill([
            '.wpforms-form input[name*="company"]',
            '.wpforms-form input[name*="organization"]',
            '.wpforms-form input[placeholder*="会社"]',
            '.wpforms-form input[placeholder*="企業"]',
        ], sender["company"])

        self._try_fill([
            '.wpforms-form input[name*="title"]',
            '.wpforms-form input[name*="position"]',
            '.wpforms-form input[placeholder*="役職"]',
        ], sender["title"])

        if self._try_fill([
            '.wpforms-form input[type="email"]',
            '.wpforms-form input[name*="email"]',
            '.wpforms-form input[placeholder*="メール"]',
        ], sender["email"]):
            filled += 1

        self._try_fill([
            '.wpforms-form input[name*="confirm"]',
            '.wpforms-form input[name*="email2"]',
            '.wpforms-form input[placeholder*="確認"]',
        ], sender["email"])

        self._try_fill([
            '.wpforms-form input[type="tel"]',
            '.wpforms-form input[name*="tel"]',
            '.wpforms-form input[name*="phone"]',
            '.wpforms-form input[placeholder*="電話"]',
        ], sender["phone"])

        if self._try_fill([
            '.wpforms-form textarea[name*="message"]',
            '.wpforms-form textarea[name*="content"]',
            '.wpforms-form textarea[name*="inquiry"]',
            '.wpforms-form textarea',
        ], self.message):
            filled += 1

        return filled >= 3
