"""
DB 유틸리티 스크립트
사용법:
  python3 db_utils.py stats              # 전체 통계
  python3 db_utils.py update NVDA 2026-05-18 203.50   # 실제 결과 입력
  python3 db_utils.py update NVDA 2026-05-18 203.50 1.2   # 벤치마크 수익률(%)도 함께 입력
  python3 db_utils.py pending            # 검증 대기 중인 예측 목록
  python3 db_utils.py list               # 전체 예측 목록
"""
import sqlite3
import sys
from datetime import datetime

DB_PATH = "/Volumes/AI/data/stock_analysis.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def calc_paper_return(action, actual_move_pct, transaction_cost_pct):
    """검증용 paper action의 총/순 수익률 계산."""
    action = action or "PAPER_CASH"
    cost = float(transaction_cost_pct or 0.0)
    if action == "PAPER_LONG":
        gross = actual_move_pct
    elif action == "PAPER_SHORT":
        gross = -actual_move_pct
    else:
        gross = 0.0

    net = gross - cost if action in ("PAPER_LONG", "PAPER_SHORT") else gross
    return gross, net


def update_actual(ticker, target_date, actual_close, benchmark_return_pct=None):
    """실제 종가 입력 → 예측 결과 자동 계산"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT id, reference_price, p10, p50, p90,
               prob_bullish, prob_neutral, prob_bearish,
               paper_action, paper_transaction_cost_pct
        FROM predictions
        WHERE ticker=? AND target_date=?
    """, (ticker, target_date))
    row = c.fetchone()

    if not row:
        print(f"예측 없음: {ticker} {target_date}")
        conn.close()
        return

    pred_id, ref_price, p10, p50, p90, pb, pn, pbear, paper_action, paper_cost = row
    actual_close = float(actual_close)
    actual_move = ((actual_close / ref_price) - 1) * 100

    # 방향 적중 여부 (p50 방향과 실제 방향 일치)
    direction_hit = 1 if (p50 >= 0) == (actual_move >= 0) else 0

    # p50 error / magnitude error
    p50_error = actual_move - p50
    magnitude_error = abs(actual_move - p50)

    # prediction interval hit
    interval_hit = 1 if p10 <= actual_move <= p90 else 0
    tail_breach = 0 if interval_hit else 1
    if interval_hit:
        tail_breach_side = None
    elif actual_move < p10:
        tail_breach_side = "below_p10"
    else:
        tail_breach_side = "above_p90"

    # realized scenario
    if actual_move > 3.0:
        realized = "bullish"
    elif actual_move < -3.0:
        realized = "bearish"
    else:
        realized = "neutral"

    # Brier score (simplified: for primary direction)
    actual_bullish = 1 if actual_move > 3.0 else 0
    brier = (pb - actual_bullish) ** 2 + (pn - (1 if -3 <= actual_move <= 3 else 0)) ** 2 + (pbear - (1 if actual_move < -3 else 0)) ** 2
    brier = brier / 3

    success = 1 if direction_hit and interval_hit else 0

    paper_gross, paper_net = calc_paper_return(paper_action, actual_move, paper_cost)
    benchmark_return = float(benchmark_return_pct) if benchmark_return_pct is not None else None
    excess_return = paper_net - benchmark_return if benchmark_return is not None else None

    c.execute("""
        UPDATE predictions SET
            actual_close=?, actual_move_pct=?, realized_scenario=?,
            direction_hit=?, magnitude_error=?, brier_score=?, success=?,
            interval_hit=?, p50_error=?, tail_breach=?, tail_breach_side=?,
            paper_gross_return_pct=?, paper_net_return_pct=?,
            benchmark_return_pct=?, excess_return_pct=?
        WHERE id=?
    """, (actual_close, actual_move, realized,
          direction_hit, magnitude_error, round(brier, 4), success,
          interval_hit, p50_error, tail_breach, tail_breach_side,
          paper_gross, paper_net, benchmark_return, excess_return,
          pred_id))

    conn.commit()
    conn.close()
    print(f"업데이트 완료: {ticker} {target_date}")
    print(f"  실제 이동: {actual_move:+.2f}% | 방향 적중: {'✓' if direction_hit else '✗'}")
    print(f"  p10~p90 구간 적중: {'✓' if interval_hit else '✗'} | p50 error: {p50_error:+.2f}%")
    print(f"  magnitude error: {magnitude_error:.2f}% | brier score: {brier:.4f}")
    print(f"  paper action: {paper_action or 'PAPER_CASH'} | net return: {paper_net:+.2f}%")


def show_stats():
    """전체 예측 성능 통계"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM predictions")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM predictions WHERE actual_close IS NOT NULL")
    validated = c.fetchone()[0]

    print(f"\n{'='*50}")
    print(f"전체 예측: {total}개 | 검증 완료: {validated}개 | 대기: {total-validated}개")

    if validated > 0:
        c.execute("""
            SELECT
                ROUND(AVG(direction_hit)*100, 1) as hit_rate,
                ROUND(AVG(interval_hit)*100, 1) as interval_hit_rate,
                ROUND(AVG(magnitude_error), 2) as avg_mag_err,
                ROUND(AVG(brier_score), 4) as avg_brier,
                ROUND(AVG(paper_net_return_pct), 2) as avg_paper_net,
                ROUND(AVG(CASE WHEN data_quality='GOOD' THEN direction_hit END)*100, 1) as good_hit,
                ROUND(AVG(CASE WHEN confidence >= 0.65 THEN direction_hit END)*100, 1) as hconf_hit
            FROM predictions WHERE actual_close IS NOT NULL
        """)
        row = c.fetchone()
        print(f"\n방향 적중률:       {row[0]}%")
        print(f"p10~p90 구간 적중률: {row[1]}%")
        print(f"평균 magnitude err: {row[2]}%")
        print(f"평균 brier score:   {row[3]}")
        print(f"평균 paper net return: {row[4]}%")
        print(f"GOOD 품질 적중률:   {row[5]}%")
        print(f"confidence≥0.65 적중률: {row[6]}%")

        print(f"\n{'─'*50}")
        print("Paper action별 성능:")
        c.execute("""
            SELECT COALESCE(paper_action, 'PAPER_CASH') as action,
                COUNT(*) as n,
                ROUND(AVG(paper_net_return_pct), 2) as avg_net,
                ROUND(AVG(direction_hit)*100, 1) as hit_rate,
                ROUND(AVG(interval_hit)*100, 1) as interval_hit_rate
            FROM predictions WHERE actual_close IS NOT NULL
            GROUP BY action ORDER BY avg_net DESC
        """)
        for row in c.fetchall():
            print(f"  {row[0]}: {row[1]}개 | 평균 순수익 {row[2]}% | 방향 {row[3]}% | 구간 {row[4]}%")

        print(f"\n{'─'*50}")
        print("종목별 성능:")
        c.execute("""
            SELECT ticker,
                COUNT(*) as n,
                ROUND(AVG(direction_hit)*100,1) as hit_rate,
                ROUND(AVG(interval_hit)*100,1) as interval_hit_rate,
                ROUND(AVG(brier_score),4) as brier,
                ROUND(AVG(paper_net_return_pct),2) as avg_net
            FROM predictions WHERE actual_close IS NOT NULL
            GROUP BY ticker ORDER BY avg_net DESC
        """)
        for row in c.fetchall():
            print(f"  {row[0]}: {row[1]}개 | 방향 {row[2]}% | 구간 {row[3]}% | brier {row[4]} | net {row[5]}%")

    conn.close()


def show_pending():
    """검증 대기 중인 예측 (target_date 지났지만 actual_close 없음)"""
    conn = get_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("""
        SELECT ticker, prediction_date, target_date, reference_price, p50, confidence, paper_action
        FROM predictions
        WHERE actual_close IS NULL AND target_date <= ?
        ORDER BY target_date
    """, (today,))
    rows = c.fetchall()
    if rows:
        print(f"\n검증 대기 ({len(rows)}개):")
        for r in rows:
            print(f"  {r[0]} | 예측일:{r[1]} | 목표일:{r[2]} | 기준가:${r[3]} | p50:{r[4]:+.1f}% | conf:{r[5]} | action:{r[6]}")
        print(f"\n입력 방법: python3 db_utils.py update TICKER YYYY-MM-DD 실제종가 [벤치마크수익률%]")
    else:
        print("검증 대기 없음.")
    conn.close()


def show_list():
    """전체 예측 목록"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT ticker, prediction_date, target_date, reference_price,
               primary_scenario, p50, confidence, data_quality,
               paper_action, actual_move_pct, direction_hit, interval_hit, paper_net_return_pct
        FROM predictions ORDER BY prediction_date DESC
    """)
    rows = c.fetchall()
    print(f"\n전체 예측 ({len(rows)}개):")
    print(f"{'티커':<6} {'예측일':<12} {'목표일':<12} {'기준가':>8} {'시나리오':<10} {'p50':>6} {'conf':>5} {'품질':<8} {'액션':<11} {'실제':>7} {'구간'} {'net':>7}")
    print("─" * 112)
    for r in rows:
        actual = f"{r[9]:+.1f}%" if r[9] is not None else "미기록"
        interval = "✓" if r[11] == 1 else ("✗" if r[11] == 0 else "-")
        net = f"{r[12]:+.1f}%" if r[12] is not None else "-"
        print(f"{r[0]:<6} {r[1]:<12} {r[2]:<12} ${r[3]:>7.2f} {r[4]:<10} {r[5]:>+5.1f}% {r[6]:>5.2f} {r[7]:<8} {str(r[8] or '-'): <11} {actual:>7} {interval} {net:>7}")
    conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "stats":
        show_stats()
    elif args[0] == "update" and len(args) in (4, 5):
        benchmark_return = args[4] if len(args) == 5 else None
        update_actual(args[1], args[2], args[3], benchmark_return)
    elif args[0] == "pending":
        show_pending()
    elif args[0] == "list":
        show_list()
    else:
        print(__doc__)
