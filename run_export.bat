@echo off
cd /d "%~dp0"
echo agent1完了後（enriched前）のリスト出力:
python export_excel.py --input data/raw_companies.csv --output data/ハイネス_営業リスト_raw.xlsx
echo.
echo agent2完了後のリスト出力:
python export_excel.py --input data/enriched_companies.csv --output data/ハイネス_営業リスト.xlsx
pause
