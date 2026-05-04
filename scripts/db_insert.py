"""
v2 분석 결과를 DB에 자동 insert
사용: python3 /Volumes/AI/scripts/db_insert.py TICKER
"""
import sqlite3
import json
import sys
import os

DB_PATH = "/Volumes/AI/data/stock_analysis.db"
BASE = "/Volumes/AI/reviews"


def default_paper_action(d):
    """이전 JSON에 paper_action이 없을 때 쓰는 deterministic fallback."""
    scenarios = d.get("scenarios", {})
    bullish = scenarios.get("bullish", {}).get("probability", 0) or 0
    bearish = scenarios.get("bearish", {}).get("probability", 0) or 0
    p50 = d.get("expected_move_distribution", {}).get("p50", 0) or 0
    confidence = d.get("confidence", 0) or 0
    data_quality = d.get("data_quality")

    is_long = (
        data_quality != "POOR"
        and confidence >= 0.55
        and bullish - bearish >= 0.15
        and p50 > 0
    )
    action = "PAPER_LONG" if is_long else "PAPER_CASH"
    return {
        "mode": "PAPER_TRADING_ONLY",
        "action": action,
        "direction": "LONG" if action == "PAPER_LONG" else "CASH",
        "entry_basis": "next_regular_session_open",
        "exit_basis": "target_date_close",
        "holding_period_trading_days": d.get("horizon_trading_days"),
        "position_size": 1.0 if action == "PAPER_LONG" else 0.0,
        "transaction_cost_pct_round_trip": 0.2 if action == "PAPER_LONG" else 0.0,
        "not_live_trade_signal": True
    }


def insert(ticker):
    ticker = ticker.upper()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    results = []

    # 1. predictions
    pred_file = f"{BASE}/{ticker}/prediction_record_v2.json"
    if os.path.exists(pred_file):
        with open(pred_file) as f:
            d = json.load(f)["prediction"]
        s = d["scenarios"]
        em = d["expected_move_distribution"]
        paper = d.get("paper_action") or default_paper_action(d)
        try:
            c.execute("""
            INSERT INTO predictions
            (ticker, prediction_date, target_date, horizon_days, reference_price,
             data_quality, confidence, primary_scenario,
             prob_bullish, prob_neutral, prob_bearish,
             p10, p50, p90,
             paper_action, paper_direction, paper_entry_basis, paper_exit_basis,
             paper_holding_days, paper_position_size, paper_transaction_cost_pct,
             pipeline_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(ticker, prediction_date, pipeline_version) DO UPDATE SET
                target_date=excluded.target_date,
                horizon_days=excluded.horizon_days,
                reference_price=excluded.reference_price,
                data_quality=excluded.data_quality,
                confidence=excluded.confidence,
                primary_scenario=excluded.primary_scenario,
                prob_bullish=excluded.prob_bullish,
                prob_neutral=excluded.prob_neutral,
                prob_bearish=excluded.prob_bearish,
                p10=excluded.p10,
                p50=excluded.p50,
                p90=excluded.p90,
                paper_action=excluded.paper_action,
                paper_direction=excluded.paper_direction,
                paper_entry_basis=excluded.paper_entry_basis,
                paper_exit_basis=excluded.paper_exit_basis,
                paper_holding_days=excluded.paper_holding_days,
                paper_position_size=excluded.paper_position_size,
                paper_transaction_cost_pct=excluded.paper_transaction_cost_pct
            WHERE predictions.actual_close IS NULL
            """, (
                d["ticker"], d["prediction_date"], d["target_date"],
                d["horizon_trading_days"], d["reference_price"],
                d["data_quality"], d["confidence"], d["primary_scenario"],
                s["bullish"]["probability"], s["neutral"]["probability"], s["bearish"]["probability"],
                em["p10"], em["p50"], em["p90"],
                paper.get("action"), paper.get("direction"),
                paper.get("entry_basis"), paper.get("exit_basis"),
                paper.get("holding_period_trading_days"),
                paper.get("position_size"),
                paper.get("transaction_cost_pct_round_trip"),
                "v2"
            ))
            results.append(f"  ✓ predictions: {ticker} {d['prediction_date']}")
        except Exception as e:
            results.append(f"  ✗ predictions: {e}")

    # 2. market_features
    feat_file = f"{BASE}/{ticker}/market_features_v2.json"
    if os.path.exists(feat_file):
        with open(feat_file) as f:
            d = json.load(f)
        p = d["price_structure"]
        t = d["trend_metrics"]
        ind = d["indicators"]
        vol = d["volume_structure"]
        vlt = d["volatility_structure"]
        mtf = d["multi_timeframe_alignment"]
        try:
            c.execute("""
            INSERT OR REPLACE INTO market_features
            (ticker, as_of, current_price, daily_change_pct,
             ema_20, ema_50, ema_200,
             price_vs_ema20_pct, price_vs_ema50_pct, price_vs_ema200_pct,
             rsi_14, macd, macd_signal, macd_histogram,
             volume_vs_avg_pct, atr_14, realized_vol_20d,
             pos_vs_20d_high_pct, pos_vs_20d_low_pct,
             daily_trend, weekly_trend, monthly_trend)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                d["ticker"], d["as_of"],
                p["current_price"], p["daily_change_pct"],
                t["ema_20"], t["ema_50"], t["ema_200"],
                t["price_vs_ema_20_pct"], t["price_vs_ema_50_pct"], t["price_vs_ema_200_pct"],
                ind["rsi_14"], ind["macd"], ind["macd_signal"], ind["macd_histogram"],
                vol["volume_vs_20d_avg_pct"], vlt["atr_14"], vlt["realized_volatility_20d"],
                p["position_vs_20d_high_pct"], p["position_vs_20d_low_pct"],
                mtf["daily"], mtf["weekly"], mtf["monthly"]
            ))
            results.append(f"  ✓ market_features: {ticker} {d['as_of']}")
        except Exception as e:
            results.append(f"  ✗ market_features: {e}")

    # 3. evidence
    ev_file = f"{BASE}/{ticker}/evidence_validated_v2.json"
    if os.path.exists(ev_file):
        with open(ev_file) as f:
            d = json.load(f)
        count = 0
        c.execute(
            "DELETE FROM evidence WHERE ticker=? AND analysis_date=?",
            (d["ticker"], d["as_of"])
        )
        for claim in d.get("validated_claims", []) + d.get("excluded_claims", []):
            try:
                c.execute("""
                INSERT INTO evidence
                (ticker, analysis_date, claim_id, category, status,
                 claim, claim_date, source_url, source_name, validation_note)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (
                    d["ticker"], d["as_of"],
                    claim.get("id"), claim.get("category"), claim.get("status"),
                    claim.get("claim"), claim.get("claim_date"),
                    claim.get("source_url"), claim.get("source_name"),
                    claim.get("validation_note") or claim.get("reason")
                ))
                count += 1
            except Exception:
                pass
        results.append(f"  ✓ evidence: {count}개 claims")

    conn.commit()
    conn.close()

    print(f"\n[DB insert] {ticker}")
    for r in results:
        print(r)
    if not results:
        print(f"  ✗ v2 파일 없음: {BASE}/{ticker}/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 db_insert.py TICKER")
    else:
        insert(sys.argv[1])
