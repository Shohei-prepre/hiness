"""
Google Drive アップロードスクリプト
data/ フォルダのCSV・Excelをアップロードする

【初回セットアップ】
1. Google Cloud Console でサービスアカウントを作成し、JSONキーをダウンロード
2. Drive の対象フォルダをサービスアカウントのメールアドレスと共有（編集者権限）
3. JSONキーの中身を GitHub Secrets の GOOGLE_SERVICE_ACCOUNT_JSON に登録
4. DRIVE_FOLDER_ID に対象フォルダのIDを設定（URLの末尾の文字列）
"""
import os
import json
import glob
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─── 設定 ──────────────────────────────────────────
# Google Drive の対象フォルダID（URLの末尾）
# 例: https://drive.google.com/drive/folders/1AbCdXXXXXXXXXX → "1AbCdXXXXXXXXXX"
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "YOUR_FOLDER_ID_HERE")

# アップロード対象ファイル
UPLOAD_PATTERNS = [
    "data/*.xlsx",
    "data/*.csv",
]

# アップロードしないファイル（中間ファイル）
EXCLUDE_FILES = {
    "raw_companies.csv",    # STEP1の生データ（不要）
}

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
# ────────────────────────────────────────────────────


def get_service():
    """サービスアカウントJSONからDriveクライアントを生成する"""
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません。\n"
            "GitHub Secrets または環境変数に設定してください。"
        )
    sa_info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def get_mimetype(path: str) -> str:
    """ファイル拡張子からMIMEタイプを返す"""
    if path.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if path.endswith(".csv"):
        return "text/csv"
    return "application/octet-stream"


def upload_file(service, filepath: str, folder_id: str) -> str:
    """ファイルをDriveにアップロードしてファイルIDを返す"""
    filename  = os.path.basename(filepath)
    mimetype  = get_mimetype(filepath)
    media     = MediaFileUpload(filepath, mimetype=mimetype, resumable=True)
    metadata  = {"name": filename, "parents": [folder_id]}

    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name",
    ).execute()
    return file.get("id", "")


def run():
    """data/ 配下のCSV・Excelを全て対象フォルダにアップロードする"""
    if DRIVE_FOLDER_ID == "YOUR_FOLDER_ID_HERE":
        print("[エラー] DRIVE_FOLDER_ID が設定されていません。")
        print("  環境変数 DRIVE_FOLDER_ID に Google Drive のフォルダIDを設定してください。")
        return

    service = get_service()

    # アップロード対象ファイルを収集
    targets = []
    for pattern in UPLOAD_PATTERNS:
        for path in glob.glob(pattern):
            if os.path.basename(path) not in EXCLUDE_FILES:
                targets.append(path)

    if not targets:
        print("[情報] アップロード対象のファイルが見つかりませんでした。")
        return

    # 日付付きサブフォルダを作成
    today = datetime.date.today().strftime("%Y-%m-%d")
    subfolder_meta = {
        "name":     today,
        "mimeType": "application/vnd.google-apps.folder",
        "parents":  [DRIVE_FOLDER_ID],
    }
    subfolder = service.files().create(body=subfolder_meta, fields="id").execute()
    subfolder_id = subfolder.get("id")
    print(f"[Drive] サブフォルダ作成: {today}/")

    # 各ファイルをアップロード
    for path in targets:
        filename = os.path.basename(path)
        print(f"  アップロード中: {filename} ...", end=" ", flush=True)
        try:
            file_id = upload_file(service, path, subfolder_id)
            print(f"完了 (id: {file_id})")
        except Exception as e:
            print(f"失敗: {e}")

    print(f"\n[完了] {len(targets)}ファイルを Drive にアップロードしました。")
    print(f"  フォルダ: https://drive.google.com/drive/folders/{subfolder_id}")


if __name__ == "__main__":
    run()
