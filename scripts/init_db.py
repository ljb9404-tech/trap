"""
stock_analysis.db 초기화 스크립트
실행: python3 /Volumes/AI/scripts/init_db.py
"""
import sqlite3
import json
import os
from pathlib import Path

DB_PATH = "/Volumes/AI/data/stock_analysis.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. predictions 테이블 — 예측 기록 + 실제 결과
    c.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker               TEXT NOT NULL,
        prediction_date      TEXT NOT NULL,
        target_date          TEXT NOT NULL,
        horizon_days         INTEGER,
        reference_price      REAL,
        data_quality         TEXT,
        confidence           REAL,
        primary_scenario     TEXT,
        prob_bullish         REAL,
        prob_neutral         REAL,
        prob_bearish         REAL,
        p10                  REAL,
        p50                  REAL,
        p90                  REAL,
        -- 실제 결과 (target_date 이후 채워짐)
        actual_close         REAL,
        actual_move_pct      REAL,
        realized_scenario    TEXT,
        direction_hit        INTEGER,
        magnitude_error      REAL,
        brier_score          REAL,
        success              INTEGER,
        pipeline_version     TEXT DEFAULT 'v2',
        created_at           TEXT DEFAULT (datetime('now')),
        UNIQUE(ticker, prediction_date, pipeline_version)
    )
    """)

    # 2. market_features 테이블 — 기술적 지표
    c.execute("""
    CREATE TABLE IF NOT EXISTS market_features (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker               TEXT NOT NULL,
        as_of                TEXT NOT NULL,
        current_price        REAL,
        daily_change_pct     REAL,
        ema_20               REAL,
        ema_50               REAL,
        ema_200              REAL,
        price_vs_ema20_pct   REAL,
        price_vs_ema50_pct   REAL,
        price_vs_ema200_pct  REAL,
        rsi_14               REAL,
        macd                 REAL,
        macd_signal          REAL,
        macd_histogram       REAL,
        volume_vs_avg_pct    REAL,
        atr_14               REAL,
        realized_vol_20d     REAL,
        pos_vs_20d_high_pct  REAL,
        pos_vs_20d_low_pct   REAL,
        daily_trend          TEXT,
        weekly_trend         TEXT,
        monthly_trend        TEXT,
        created_at           TEXT DEFAULT (datetime('now')),
        UNIQUE(ticker, as_of)
    )
    """)

    # 3. evidence 테이블 — 검증된 근거
    c.execute("""
    CREATE TABLE IF NOT EXISTS evidence (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker               TEXT NOT NULL,
        analysis_date        TEXT NOT NULL,
        claim_id             TEXT,
        category             TEXT,
        status               TEXT,
        claim                TEXT,
        claim_date           TEXT,
        source_url           TEXT,
        source_name          TEXT,
        validation_note      TEXT,
        created_at           TEXT DEFAULT (datetime('now'))
    )
    """)

    # 4. validation_summary 테이블 — 백테스팅 통계
    c.execute("""
    CREATE TABLE IF NOT EXISTS validation_summary (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        as_of                TEXT NOT NULL,
        total_predictions    INTEGER,
        direction_hit_rate   REAL,
        avg_magnitude_error  REAL,
        avg_brier_score      REAL,
        good_quality_hit_rate   REAL,
        marginal_quality_hit_rate REAL,
        high_confidence_hit_rate  REAL,
        created_at           TEXT DEFAULT (datetime('now'))
    )
    """)

    conn.commit()
    conn.close()
    print(f"DB 초기화 완료: {DB_PATH}")
    print("테이블: predictions, market_features, evidence, validation_summary")


def import_nvda_v2():
    """기존 NVDA v2 파일을 DB에 import"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. prediction_record_v2.json import
    pred_file = "/Volumes/AI/reviews/NVDA/prediction_record_v2.json"
    if os.path.exists(pred_file):
        with open(pred_file) as f:
            d = json.load(f)["prediction"]
        s = d["scenarios"]
        em = d["expected_move_distribution"]
        v = d["validation"]
        try:
            c.execute("""
            INSERT OR IGNORE INTO predictions
            (ticker, prediction_date, target_date, horizon_days, reference_price,
             data_quality, confidence, primary_scenario,
             prob_bullish, prob_neutral, prob_bearish,
             p10, p50, p90,
             actual_close, actual_move_pct, realized_scenario,
             direction_hit, magnitude_error, brier_score, success,
             pipeline_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                d["ticker"], d["prediction_date"], d["target_date"],
                d["horizon_trading_days"], d["reference_price"],
                d["data_quality"], d["confidence"], d["primary_scenario"],
                s["bullish"]["probability"], s["neutral"]["probability"], s["bearish"]["probability"],
                em["p10"], em["p50"], em["p90"],
                v["actual_close_on_target_date"], v["actual_move_pct"],
                v["realized_scenario"], v["direction_hit"],
                v["magnitude_error"], v["brier_score"], v["success"],
                "v2"
            ))
            print(f"  predictions: NVDA 2026-05-04 import 완료")
        except Exception as e:
            print(f"  predictions import 오류: {e}")

    # 2. market_features_v2.json import
    feat_file = "/Volumes/AI/reviews/NVDA/market_features_v2.json"
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
            INSERT OR IGNORE INTO market_features
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
            print(f"  market_features: NVDA 2026-05-04 import 완료")
        except Exception as e:
            print(f"  market_features import 오류: {e}")

    # 3. evidence_validated_v2.json import
    ev_file = "/Volumes/AI/reviews/NVDA/evidence_validated_v2.json"
    if os.path.exists(ev_file):
        with open(ev_file) as f:
            d = json.load(f)
        count = 0
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
            except Exception as e:
                print(f"  evidence import 오류 ({claim.get('id')}): {e}")
        print(f"  evidence: {count}개 claims import 완료")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("\nNVDA v2 데이터 import 중...")
    import_nvda_v2()
    print("\n완료.")
