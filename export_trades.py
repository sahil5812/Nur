"""
export_trades.py — One-click command to export all Nur Bot trades to Excel & CSV.

Usage:
    python export_trades.py
"""

from pathlib import Path
from utils.excel_exporter import export_trades_to_excel

if __name__ == "__main__":
    print("=" * 60)
    print("  📊 NUR TRADING BOT — EXCEL JOURNAL EXPORTER")
    print("=" * 60)
    xlsx_path, csv_path = export_trades_to_excel()
    print(f"\n  ✅ Excel File Generated:  {xlsx_path}")
    print(f"  ✅ CSV File Generated:    {csv_path}")
    print("\n  Summary: All trade history, PnL, outcomes, and statistics have been saved.")
    print("  You can double-click the .xlsx file to open it directly in Microsoft Excel!")
    print("=" * 60)
