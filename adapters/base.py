"""フォームアダプター基底クラス"""
from abc import ABC, abstractmethod
from playwright.sync_api import Page
from config import SENDER_INFO, MESSAGE_OPENING, MESSAGE_VALUE, MESSAGE_CLOSING


def build_full_message(target_company: str, personalized_body: str) -> str:
    """3ブロックを結合して完全なメッセージを生成する"""
    info = {**SENDER_INFO, "target_company": target_company}
    return "\n\n".join([
        MESSAGE_OPENING.format(**info),
        personalized_body,
        MESSAGE_VALUE,
        MESSAGE_CLOSING.format(**info),
    ])


class BaseAdapter(ABC):
    """全フォームアダプターの基底クラス"""

    def __init__(self, page: Page, company_name: str, personalized_body: str, dry_run: bool = True):
        self.page         = page
        self.company_name = company_name
        self.message      = build_full_message(company_name, personalized_body)
        self.sender       = SENDER_INFO
        self.dry_run      = dry_run

    @abstractmethod
    def detect(self) -> bool:
        """このアダプターが対応するフォーム種別か判定する"""
        pass

    @abstractmethod
    def fill(self) -> bool:
        """フォームフィールドを入力する。成功時True"""
        pass

    def submit(self) -> bool:
        """送信ボタンをクリックする（dry_run=Trueの場合は何もしない）"""
        if self.dry_run:
            return True
        for sel in [
            'input[type="submit"]',
            'button[type="submit"]',
            'button:has-text("送信")',
            'button:has-text("確認")',
            'button:has-text("Send")',
            'button:has-text("Submit")',
            'button:has-text("次へ")',
        ]:
            btn = self.page.locator(sel).first
            if btn.count() > 0:
                btn.click()
                return True
        return False

    def _try_fill(self, selectors: list[str], value: str) -> bool:
        """セレクタリストを順番に試してフィールドを入力する"""
        for sel in selectors:
            try:
                el = self.page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    el.fill(value)
                    return True
            except Exception:
                continue
        return False

    def _try_select(self, selectors: list[str], value_keywords: list[str]) -> bool:
        """セレクトボックスで最初にマッチする選択肢を選ぶ"""
        for sel in selectors:
            try:
                el = self.page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    options = el.locator("option").all_text_contents()
                    for kw in value_keywords:
                        for opt in options:
                            if kw in opt:
                                el.select_option(label=opt)
                                return True
            except Exception:
                continue
        return False
