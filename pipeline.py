"""
パイプライン CLIオーケストレーター
各STEPを順番に実行する
"""
import argparse
import os
import sys


def step1(industry: str):
    """STEP1: リサーチ（企業名 + 公式URL収集）"""
    print("\n" + "="*50)
    print("STEP1: リサーチ開始")
    print("="*50)
    import agent1_research
    agent1_research.run()


def step2(industry: str):
    """STEP2: フォームURL発見"""
    print("\n" + "="*50)
    print("STEP2: フォームURL発見開始")
    print("="*50)
    import agent2_enrich
    agent2_enrich.run()


def step2_5(industry: str):
    """STEP2.5: Gemini APIでパーソナライズ本文生成"""
    print("\n" + "="*50)
    print("STEP2.5: Geminiパーソナライズ開始")
    print("="*50)
    import agent_personalize
    agent_personalize.run(industry)


def step3():
    """STEP3: ドライラン（入力のみ、送信なし）"""
    print("\n" + "="*50)
    print("STEP3: ドライラン開始")
    print("="*50)
    import agent3_dryrun
    agent3_dryrun.run(dry_run=True)


def step4():
    """STEP4: 実際の送信"""
    print("\n" + "="*50)
    print("STEP4: フォーム送信開始")
    print("="*50)
    import agent4_submit
    agent4_submit.run()


def export_excel():
    """Excelエクスポート"""
    print("\n" + "="*50)
    print("Excelエクスポート")
    print("="*50)
    os.system("python export_excel.py")


def main():
    parser = argparse.ArgumentParser(
        description="ハイネス 営業フォーム自動送信パイプライン",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
実行例:
  python pipeline.py --steps 1 2          # STEP1とSTEP2を実行
  python pipeline.py --steps 1 2 2.5 3    # STEP1〜3を実行（送信なし）
  python pipeline.py --steps all          # 全ステップ実行
  python pipeline.py --steps 4            # 送信のみ実行
  python pipeline.py --industry 人材紹介  # 業界を指定
        """,
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        default=["1", "2"],
        help='実行するステップ: 1 / 2 / 2.5 / 3 / 4 / all (デフォルト: 1 2)',
    )
    parser.add_argument(
        "--industry",
        default="求人広告代理店",
        help="対象業界名（Geminiプロンプトに使用）",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="実行後にExcelをエクスポートする",
    )
    args = parser.parse_args()

    steps = args.steps
    if "all" in steps:
        steps = ["1", "2", "2.5", "3", "4"]

    os.makedirs("data", exist_ok=True)

    for step in steps:
        if step == "1":
            step1(args.industry)
        elif step == "2":
            step2(args.industry)
        elif step in ("2.5", "25"):
            step2_5(args.industry)
        elif step == "3":
            step3()
        elif step == "4":
            step4()
        else:
            print(f"[警告] 不明なステップ: {step} → スキップ")

    if args.export:
        export_excel()

    print("\n[パイプライン完了]")


if __name__ == "__main__":
    main()
