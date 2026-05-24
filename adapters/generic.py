"""汎用フォームアダプター（フォールバック）"""
from playwright.sync_api import Page
from .base import BaseAdapter


class GenericAdapter(BaseAdapter):
    """キーワードマッチングで任意のフォームを入力する汎用アダプター"""

    def detect(self) -> bool:
        """常にTrueを返す（他のアダプターが全て失敗した場合のフォールバック）"""
        return True

    def fill(self) -> bool:
        sender = self.sender
        filled = 0

        # 名前
        if self._try_fill([
            'input[name*="name"]:not([name*="company"]):not([name*="kana"]):not([name*="yomi"])',
            'input[placeholder*="名前"]:not([placeholder*="会社"]):not([placeholder*="ふりがな"])',
            'input[placeholder*="お名前"]',
            'input[id*="name"]:not([id*="company"]):not([id*="kana"])',
            'input[name="your-name"]',
            'input[name="氏名"]',
        ], sender["name"]):
            filled += 1

        # ふりがな（存在する場合のみ）
        self._try_fill([
            'input[name*="kana"]',
            'input[name*="yomi"]',
            'input[name*="furigana"]',
            'input[placeholder*="ふりがな"]',
            'input[placeholder*="フリガナ"]',
            'input[placeholder*="よみ"]',
        ], sender["name_kana"])

        # 会社名
        if self._try_fill([
            'input[name*="company"]',
            'input[name*="corp"]',
            'input[placeholder*="会社"]',
            'input[placeholder*="企業"]',
            'input[placeholder*="組織"]',
            'input[id*="company"]',
            'input[name="会社名"]',
        ], sender["company"]):
            filled += 1

        # 役職
        self._try_fill([
            'input[name*="title"]',
            'input[name*="position"]',
            'input[name*="post"]',
            'input[placeholder*="役職"]',
            'input[placeholder*="担当"]',
            'input[id*="title"]',
        ], sender["title"])

        # メールアドレス
        if self._try_fill([
            'input[type="email"]',
            'input[name*="email"]',
            'input[name*="mail"]',
            'input[placeholder*="メール"]',
            'input[placeholder*="mail"]',
            'input[placeholder*="Email"]',
            'input[id*="email"]',
        ], sender["email"]):
            filled += 1

        # メールアドレス確認
        self._try_fill([
            'input[name*="email_confirm"]',
            'input[name*="email2"]',
            'input[name*="confirm"]',
            'input[placeholder*="確認"]',
        ], sender["email"])

        # 電話番号
        self._try_fill([
            'input[type="tel"]',
            'input[name*="tel"]',
            'input[name*="phone"]',
            'input[placeholder*="電話"]',
            'input[placeholder*="tel"]',
            'input[placeholder*="Tel"]',
            'input[id*="tel"]',
        ], sender["phone"])

        # URL
        self._try_fill([
            'input[name*="url"]',
            'input[name*="website"]',
            'input[name*="homepage"]',
            'input[placeholder*="URL"]',
            'input[placeholder*="サイト"]',
        ], sender["url"])

        # お問い合わせ種別（セレクトボックス）
        self._try_select(
            ['select[name*="type"]', 'select[name*="category"]', 'select[name*="kind"]',
             'select[id*="type"]', 'select[name*="subject"]'],
            ["その他", "ビジネス", "法人", "企業", "サービス", "導入", "other", "Other"],
        )

        # メッセージ本文（最重要）
        if self._try_fill([
            'textarea[name*="message"]',
            'textarea[name*="content"]',
            'textarea[name*="inquiry"]',
            'textarea[name*="body"]',
            'textarea[name*="text"]',
            'textarea[name*="comment"]',
            'textarea[placeholder*="お問い合わせ"]',
            'textarea[placeholder*="内容"]',
            'textarea[placeholder*="メッセージ"]',
            'textarea[placeholder*="ご用件"]',
            'textarea',
        ], self.message):
            filled += 1

        # 最低限：名前・メール・本文の3つが入力できていればOK
        return filled >= 3
