"""
utils/excel_exporter.py — Automated Excel & CSV Trade Journal Exporter for Nur Bot.

Features:
  - Real-time auto-logging of every closed trade to Excel (.xlsx) and CSV (.csv).
  - Professional institutional styling with openpyxl:
      * Sheet 1: "Trade History" with emerald green for wins, crimson for losses.
      * Sheet 2: "Executive Summary" with Total PnL, Win Rate, Profit Factor, Best/Worst trades.
  - Standalone and callable from database/stats_db.py or API.
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from utils.logger import get_logger

logger = get_logger(__name__)

# Default reports directory in both local and workspace paths
_BASE_DIR = Path(__file__).resolve().parent.parent
_REPORTS_DIR = _BASE_DIR / "reports"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_XLSX_PATH = _REPORTS_DIR / "nur_trading_journal.xlsx"
DEFAULT_CSV_PATH = _REPORTS_DIR / "trading_journal.csv"


def export_trades_to_excel(
    db_path: Path | str | None = None,
    output_xlsx: Path | str | None = None,
    output_csv: Path | str | None = None,
) -> tuple[Path, Path]:
    """
    Reads all historical trades from SQLite and generates formatted Excel and CSV journals.
    Returns (xlsx_path, csv_path).
    """
    if db_path is None:
        from config import DB_PATH
        db_path = DB_PATH

    xlsx_path = Path(output_xlsx) if output_xlsx else DEFAULT_XLSX_PATH
    csv_path = Path(output_csv) if output_csv else DEFAULT_CSV_PATH

    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Fetch trades from DB
    conn = sqlite3.connect(str(db_path))
    query = """
        SELECT 
            id, user_id, trade_id, direction, 
            entry_price, exit_price, sl, lot, score, 
            pnl, exit_reason, is_paper, entry_time, exit_time, 
            session, regime
        FROM trades
        ORDER BY id ASC
    """
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as exc:
        logger.error(f"Error fetching trades for Excel export: {exc}")
        df = pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        # Create empty template
        cols = [
            "Trade ID", "User ID", "Direction", "Lot Size", "Entry Price",
            "Exit Price", "Stop Loss", "PnL (Profit/Loss)", "Outcome",
            "Exit Reason", "AI Score", "Session", "Regime", "Mode",
            "Entry Time", "Exit Time"
        ]
        empty_df = pd.DataFrame(columns=cols)
        empty_df.to_csv(csv_path, index=False)
        empty_df.to_excel(xlsx_path, index=False, sheet_name="Trade History")
        return xlsx_path, csv_path

    # 2. Enrich DataFrame with human-readable columns
    df["trade_id"] = df["trade_id"].fillna(df["id"].apply(lambda x: f"T-{x:04d}"))
    df["Outcome"] = df["pnl"].apply(lambda p: "WIN" if p > 0 else ("BREAKEVEN" if p == 0 else "LOSS"))
    df["Mode"] = df["is_paper"].apply(lambda p: "Paper/Demo" if p else "Real Money")

    rename_map = {
        "id": "Record #",
        "trade_id": "Trade ID",
        "user_id": "User ID",
        "direction": "Direction",
        "lot": "Lot Size",
        "entry_price": "Entry Price",
        "exit_price": "Exit Price",
        "sl": "Stop Loss",
        "pnl": "PnL",
        "exit_reason": "Exit Reason",
        "score": "AI Score",
        "session": "Session",
        "regime": "Market Regime",
        "entry_time": "Entry Time",
        "exit_time": "Exit Time",
    }
    export_df = df.rename(columns=rename_map)

    column_order = [
        "Record #", "Trade ID", "Direction", "Lot Size", "Entry Price",
        "Exit Price", "Stop Loss", "PnL", "Outcome", "Exit Reason",
        "AI Score", "Session", "Market Regime", "Mode", "Entry Time", "Exit Time"
    ]
    present_cols = [c for c in column_order if c in export_df.columns]
    export_df = export_df[present_cols]

    # Export clean CSV
    export_df.to_csv(csv_path, index=False)

    # 3. Calculate Executive Summary Metrics
    total_trades = len(df)
    wins = len(df[df["pnl"] > 0])
    losses = len(df[df["pnl"] < 0])
    breakevens = len(df[df["pnl"] == 0])
    win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
    total_pnl = df["pnl"].sum()
    gross_win = df[df["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(df[df["pnl"] < 0]["pnl"].sum())
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 1.0)
    best_win = df["pnl"].max() if not df.empty else 0.0
    worst_loss = df["pnl"].min() if not df.empty else 0.0
    avg_trade = df["pnl"].mean() if not df.empty else 0.0

    summary_data = [
        {"Metric": "Platform / Bot", "Value": "NUR Institutional Trading System"},
        {"Metric": "Asset / Symbol", "Value": "XAUUSD (Gold Spot)"},
        {"Metric": "Report Generated", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Metric": "Total Trades Executed", "Value": total_trades},
        {"Metric": "Winning Trades", "Value": wins},
        {"Metric": "Losing Trades", "Value": losses},
        {"Metric": "Breakeven Trades", "Value": breakevens},
        {"Metric": "Win Rate (%)", "Value": f"{win_rate:.2f}%"},
        {"Metric": "Profit Factor", "Value": f"{profit_factor:.2f}"},
        {"Metric": "Total Realized PnL", "Value": f"{total_pnl:+.2f}"},
        {"Metric": "Average Trade Expectancy", "Value": f"{avg_trade:+.2f}"},
        {"Metric": "Peak Single Win", "Value": f"{best_win:+.2f}"},
        {"Metric": "Worst Single Loss", "Value": f"{worst_loss:+.2f}"},
        {"Metric": "Gross Wins Total", "Value": f"{gross_win:+.2f}"},
        {"Metric": "Gross Losses Total", "Value": f"{gross_loss:+.2f}"},
    ]
    summary_df = pd.DataFrame(summary_data)

    # 4. Write Styled Excel with openpyxl
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Executive Summary", index=False)
        export_df.to_excel(writer, sheet_name="Trade History", index=False)

        # Style Sheets
        wb = writer.book

        # Palette
        header_fill = PatternFill(start_color="10141D", end_color="10141D", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        accent_font = Font(name="Calibri", size=11, bold=True, color="D4AF37") # Gold
        win_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid") # Light emerald
        loss_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid") # Light crimson
        be_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
        win_text = Font(color="007A3D", bold=True)
        loss_text = Font(color="C62828", bold=True)
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        # Style Summary Sheet
        ws_sum = wb["Executive Summary"]
        for col_idx in range(1, 3):
            cell = ws_sum.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="left", vertical="center")
        ws_sum.column_dimensions["A"].width = 30
        ws_sum.column_dimensions["B"].width = 35

        for r in range(2, len(summary_data) + 2):
            c_val = ws_sum.cell(row=r, column=2)
            c_label = ws_sum.cell(row=r, column=1)
            c_label.font = Font(bold=True, color="333333")
            if "Total Realized PnL" in str(c_label.value):
                c_val.font = Font(bold=True, size=12, color="007A3D" if total_pnl >= 0 else "C62828")

        # Style Trade History Sheet
        ws_hist = wb["Trade History"]
        # Format Headers
        for col_idx in range(1, len(present_cols) + 1):
            cell = ws_hist.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        pnl_col_idx = present_cols.index("PnL") + 1 if "PnL" in present_cols else None
        outcome_col_idx = present_cols.index("Outcome") + 1 if "Outcome" in present_cols else None

        for row_idx in range(2, len(export_df) + 2):
            if pnl_col_idx:
                pnl_cell = ws_hist.cell(row=row_idx, column=pnl_col_idx)
                try:
                    val = float(pnl_cell.value)
                    if val > 0:
                        pnl_cell.fill = win_fill
                        pnl_cell.font = win_text
                    elif val < 0:
                        pnl_cell.fill = loss_fill
                        pnl_cell.font = loss_text
                    else:
                        pnl_cell.fill = be_fill
                except (ValueError, TypeError):
                    pass

            for c in range(1, len(present_cols) + 1):
                ws_hist.cell(row=row_idx, column=c).border = thin_border

        # Auto-adjust column widths
        for col in ws_hist.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_hist.column_dimensions[col_letter].width = max(max_len + 3, 12)

    logger.info(f"✅ Excel Trading Journal exported successfully → {xlsx_path}")
    return xlsx_path, csv_path


def append_trade_to_journal(trade_dict: dict[str, Any]) -> None:
    """
    Appends a single newly closed trade to both CSV and regenerates the Excel journal.
    Called automatically on every trade completion.
    """
    try:
        from config import DB_PATH
        export_trades_to_excel(db_path=DB_PATH)
    except Exception as exc:
        logger.warning(f"Failed to auto-update Excel trade journal: {exc}")
