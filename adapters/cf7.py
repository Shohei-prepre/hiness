"""Contact Form 7 アダプター"""
from .base import BaseAdapter


class CF7Adapter(BaseAdapter):
    """WordPress Contact Form 7 専用アダプター"""

    def detect(self) -> bool:
        """ページに wpcf7 クラスが存在するか確認する"""
        return self.page.locator(".wpcf7, .wpcf7-form, form.wpcf7-form").count() > 0

    def fill(self) -> bool:
        sender = self.sender
        filled = 0

        if self._try_fill([
            'input[name="your-name"]', 'input[name="name"]',
            '.wpcf7-form input[name*="name"]:not([name*="kana"])',
        ], sender["name"]):
            filled += 1

        self._try_fill([
            'input[name*="kana"]', 'input[name*="yomi"]', 'input[name*="furigana"]',
        ], sender["name_kana"])

        self._try_fill([
            'input[name="your-company"]', 'input[name="company"]',
            '.wpcf7-form input[name*="company"]',
        ], sender["company"])

        if self._try_fill([
            'input[name="your-email"]', 'input[name="email"]',
            '.wpcf7-form input[type="email"]',
        ], sender["email"]):
            filled += 1

        self._try_fill([
            'input[name="your-email-2"]', 'input[name="email-confirm"]',
        ], sender["email"])

        self._try_fill([
            'input[name="your-tel"]', 'input[name="tel"]',
            '.wpcf7-form input[type="tel"]',
        ], sender["phone"])

        if self._try_fill([
            'textarea[name="your-message"]', 'textarea[name="message"]',
            '.wpcf7-form textarea',
        ], self.message):
            filled += 1

        return filled >= 3
