"""アダプターファクトリー：フォーム種別を自動判定して適切なアダプターを返す"""
from playwright.sync_api import Page
from .base import BaseAdapter
from .cf7 import CF7Adapter
from .wpforms import WPFormsAdapter
from .mwwpform import MWWPFormAdapter
from .generic import GenericAdapter


def get_adapter(page: Page, company_name: str, personalized_body: str, dry_run: bool = True) -> BaseAdapter:
    """優先順位順にアダプターを試し、最初にdetect()がTrueを返したものを使用する"""
    candidates = [
        CF7Adapter,
        WPFormsAdapter,
        MWWPFormAdapter,
        GenericAdapter,   # 必ずTrueを返すフォールバック
    ]
    for cls in candidates:
        adapter = cls(page, company_name, personalized_body, dry_run)
        if adapter.detect():
            return adapter
    # GenericAdapterが常にTrueを返すため、ここには到達しない
    return GenericAdapter(page, company_name, personalized_body, dry_run)
