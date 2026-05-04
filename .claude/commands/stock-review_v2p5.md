# stock-review v2.5

**목적:** v2 예측 연구 파이프라인에 로컬 Python 기반 Historical Feature Distribution Lite를 추가한 버전  
**사용법:** `/stock-review_v2p5 TICKER`  
**예시:** `/stock-review_v2p5 PLTR`, `/stock-review_v2p5 NVDA`, `/stock-review_v2p5 005930`

---

## 핵심 원칙

이 파이프라인은 매매 주문이나 자동매매 신호를 생성하지 않는다.
목적은 예측 가능한 형태의 시장 가설을 만들고, 시간이 지나면 실제 결과와 비교할 수 있도록 기록하는 것이다.

v2.5의 추가 목표는 현재 feature 조합이 과거에 어떤 forward return 분포를 만들었는지 확인하는 것이다.
이 계산은 AI가 추정하지 않고 로컬 Python으로 수행한다.

**AI는 예언자가 아니라 추론 보조 도구다.**
좋은 분석은 수익을 보장하지 않는다.
일관된 기록과 검증이 복잡한 예측보다 중요하다.

### 목표

- 측정 가능한 시장 feature 추출
- 근거 기반 기업/섹터/매크로 evidence 수집
- 출처 검증 및 stale 데이터 제거
- 로컬 Python으로 historical feature distribution 계산
- bullish / neutral / bearish 확률 시나리오 생성
- 예측 로그 축적
- 30~50개 예측마다 성능 검증

### 공통 규칙

- 매수/매도 추천 금지
- 자동 주문, 진입가, 손절가, 포지션 사이징 생성 금지
- 방향성 표현은 GPT 확률 시나리오 단계에서만 허용
- 검증되지 않은 정보는 예측에 반영하지 않는다
- 모든 수치에는 날짜와 출처를 남긴다
- 모든 시나리오 확률 합계는 100%여야 한다
- neutral/base scenario를 반드시 포함한다
- JSON 산출물이 필요한 단계는 JSON only를 지킨다
- 과거 분포 확률은 반드시 Python 계산 결과에서 가져온다
- sample_size가 부족한 통계는 확률 근거로 사용하지 않는다

---

## 데이터 신뢰도 등급

| 등급 | 의미 | 예측 반영 |
|------|------|-----------|
| VERIFIED | 원문 URL, 공식 자료, TradingView MCP, SEC, 실적 발표 자료 등으로 직접 확인 | 반영 가능 |
| PARTIALLY_VERIFIED | 출처는 있으나 원문 일부만 확인되거나 2차 매체 보도에 의존 | 제한 반영 |
| STALE | 데이터 유형별 유효기간 초과 | 예측 반영 제외, 참고만 가능 |
| UNSUPPORTED | 출처 없음, 접속 불가, 주장 검증 불가 | 완전 제외 |
| CONTRADICTED | 출처 내용과 주장이 불일치 | 완전 제외 및 플래그 |

### STALE 기준

| 데이터 유형 | stale 기준 |
|-------------|------------|
| Earnings data | 최근 분기 또는 120일 초과 |
| Guidance revisions | 90일 초과 |
| Analyst revisions | 45일 초과 |
| Insider activity | 90일 초과 |
| Institutional activity | 최신 13F 기준, 단 120일 초과 시 stale |
| Macro data | 최신 발표치가 아닌 경우 stale |
| Sector news | 30일 초과 |
| Options-related news | 7일 초과 |
| Price/volume/indicator data | TradingView MCP 최신 데이터만 사용 |
| Historical OHLCV | 동일 데이터 소스에서 받은 일봉 데이터만 사용 |

---

## Historical Feature Distribution Lite 원칙

이 단계는 API 사용료를 늘리지 않기 위해 로컬 Python으로만 계산한다.
과거 OHLCV는 TradingView MCP 또는 이미 저장된 CSV를 사용하고, LLM에게 원시 과거 데이터를 통째로 분석시키지 않는다.

### 사용 feature

| feature | 정의 |
|---------|------|
| RSI bucket | RSI 14 구간 |
| EMA distance bucket | 현재가와 EMA20, EMA50의 거리 |
| Volume expansion bucket | 현재 거래량 / 20일 평균 거래량 |
| Relative strength bucket | 티커 20일 수익률 - 벤치마크 20일 수익률 |

### 표본 수 규칙

| sample_size | 사용 규칙 |
|-------------|-----------|
| < 50 | INSUFFICIENT_SAMPLE. 확률 산정 근거로 사용 금지 |
| 50~99 | REFERENCE_ONLY. 참고용, 시나리오 보조 가중치 최대 0.15 |
| >= 100 | USABLE_AS_ANCHOR. 시나리오 보조 가중치 최대 0.35 |

### 매칭 완화 규칙

먼저 엄격한 feature 조합으로 과거 유사 구간을 찾고, 표본이 부족할 때만 정해진 순서로 완화한다.

| tier | 조건 |
|------|------|
| A_exact | RSI + EMA20 distance + volume expansion + relative strength |
| B_drop_volume | RSI + EMA20 distance + relative strength |
| C_rsi_rs_only | RSI + relative strength |

단, 어떤 tier에서도 `sample_size < 50`이면 통계 기반 확률을 생성하지 않는다.

---

## 파일 경로 규칙

모든 파일은 티커별 디렉토리에 저장한다. 여러 종목 동시 실행 시 충돌을 피한다.

```
./reports/{ticker}.md                              ← 사람이 읽는 요약 보고서
./reviews/{TICKER}/market_features.json            ← TradingView feature 추출
./reviews/{TICKER}/ohlcv_daily.csv                 ← 티커 일봉 OHLCV
./reviews/{TICKER}/benchmark_ohlcv_daily.csv       ← 벤치마크 일봉 OHLCV
./reviews/{TICKER}/evidence_raw.json               ← Gemini evidence 원본 수집
./reviews/{TICKER}/evidence_validated.json         ← Claude evidence 검증 결과
./reviews/{TICKER}/feature_distribution_lite.json  ← Python 과거 feature 분포 계산
./reviews/{TICKER}/scenario_forecast.json          ← GPT 확률 시나리오
./reviews/{TICKER}/prediction_record.json          ← 단일 예측 기록
./reviews/{TICKER}/final_review.md                 ← 최종 예측 리뷰
./logs/predictions/{TICKER}_{YYYYMMDD}.json        ← 누적 검증용 예측 로그
./logs/prediction_log.md                           ← 사람이 읽는 예측 로그
./logs/validation_summary.md                       ← 30~50개 단위 검증 요약
./scripts/feature_distribution_lite.py             ← 로컬 Python 계산 스크립트
```

---

## 파이프라인 (7단계)

`$ARGUMENTS`에서 티커를 추출한다. 없으면 사용자에게 묻는다.
이하 `{TICKER}` = 대문자, `{ticker}` = 소문자.

디렉토리 생성:
```bash
mkdir -p ./reports ./reviews/{TICKER} ./logs/predictions ./scripts
```

---

### STEP 1 — Claude: TradingView MCP Feature Extraction

Claude는 트레이더가 아니다.
Claude는 시장 feature 추출 엔진이다.

TradingView MCP를 통해 최신 시장 데이터를 수집하고, 방향성 예측 없이 측정 가능한 feature만 추출한다.

**STRICT RULES**

- 방향 예측 금지
- bullish/bearish 표현 금지
- 주관적 차트 패턴 해석 금지
- 매매 조언 금지
- 오직 측정 가능한 데이터만 출력
- JSON only

**수집 항목**

1. Price structure
2. Volume structure
3. Volatility structure
4. Trend metrics
5. Multi-timeframe alignment
6. Relative strength
7. Key support/resistance levels
8. Indicator values
9. Historical daily OHLCV for ticker
10. Historical daily OHLCV for benchmark

**Historical OHLCV 수집 규칙**

- 최소 3년, 가능하면 5년 이상의 일봉 데이터를 수집한다.
- 티커 OHLCV는 `./reviews/{TICKER}/ohlcv_daily.csv`에 저장한다.
- 벤치마크 OHLCV는 `./reviews/{TICKER}/benchmark_ohlcv_daily.csv`에 저장한다.
- 미국 주식 기본 벤치마크는 `SPY`를 사용한다.
- 한국 주식은 가능한 경우 `KOSPI` 또는 `EWY`를 사용하고, 불가능하면 `SPY`를 사용한다.
- CSV 컬럼은 반드시 `date,open,high,low,close,volume` 순서를 사용한다.
- 과거 OHLCV를 수집할 수 없으면 Python feature distribution 단계는 `DATA_MISSING`으로 처리한다.

**출력 JSON 형식**

```json
{
  "ticker": "{TICKER}",
  "as_of": "YYYY-MM-DD",
  "source": "TradingView MCP",
  "benchmark_symbol": "SPY",
  "price_structure": {
    "current_price": 0.0,
    "daily_change_pct": 0.0,
    "position_vs_20d_high_pct": 0.0,
    "position_vs_20d_low_pct": 0.0,
    "position_vs_100d_high_pct": 0.0,
    "position_vs_100d_low_pct": 0.0
  },
  "volume_structure": {
    "current_volume": 0,
    "avg_20d_volume": 0,
    "volume_vs_20d_avg_pct": 0.0
  },
  "volatility_structure": {
    "atr_14": 0.0,
    "atr_pct": 0.0,
    "realized_volatility_20d": 0.0
  },
  "trend_metrics": {
    "ema_20": 0.0,
    "ema_50": 0.0,
    "ema_200": 0.0,
    "price_vs_ema_20_pct": 0.0,
    "price_vs_ema_50_pct": 0.0,
    "price_vs_ema_200_pct": 0.0
  },
  "multi_timeframe_alignment": {
    "daily": "",
    "weekly": "",
    "monthly": ""
  },
  "relative_strength": {
    "vs_benchmark_20d_pct": 0.0,
    "benchmark_symbol": "SPY"
  },
  "support_resistance": {
    "support_levels": [],
    "resistance_levels": []
  },
  "indicators": {
    "rsi_14": 0.0,
    "macd": 0.0,
    "macd_signal": 0.0,
    "macd_histogram": 0.0
  },
  "historical_data": {
    "ticker_ohlcv_path": "./reviews/{TICKER}/ohlcv_daily.csv",
    "benchmark_ohlcv_path": "./reviews/{TICKER}/benchmark_ohlcv_daily.csv",
    "daily_bars": 0,
    "status": "AVAILABLE | PARTIAL | DATA_MISSING"
  },
  "missing_fields": []
}
```

저장:
`./reviews/{TICKER}/market_features.json`

사람이 읽는 간단한 feature 요약도 저장:
`./reports/{ticker}.md`

---

### STEP 2 — Gemini CLI: Evidence Collection

Gemini는 의견을 내지 않는다.
Gemini는 evidence 수집 엔진이다.

Google Search를 활용해 티커와 관련된 사실 기반 자료만 수집한다.

다음 프롬프트를 `./claude/gemini_evidence_{TICKER}.md`에 저장한다.

```
You are an evidence collection engine.

Ticker: {TICKER}
As-of date: YYYY-MM-DD

Your task:
Collect factual evidence related to the ticker.

STRICT RULES:
- No opinions
- No emotional interpretation
- No unsupported conclusions
- Every claim must include a source URL
- Every numerical claim must include value, date, and source
- Do not label anything VERIFIED
- Do not generate trading advice
- Output JSON only

Collect:
1. Earnings data
2. Guidance revisions
3. Analyst revisions
4. Insider activity
5. Institutional activity
6. Relevant macro exposure
7. Relevant sector news
8. Options-related news if available

Freshness rules:
- Earnings data: latest quarter or within 120 days
- Guidance revisions: within 90 days
- Analyst revisions: within 45 days
- Insider activity: within 90 days
- Institutional activity: latest 13F, stale if older than 120 days
- Macro data: latest official release
- Sector news: within 30 days
- Options-related news: within 7 days

Output schema:
{
  "ticker": "{TICKER}",
  "as_of": "YYYY-MM-DD",
  "claims": [
    {
      "id": "EARNINGS_001",
      "category": "earnings | guidance_revision | analyst_revision | insider_activity | institutional_activity | macro_exposure | sector_news | options_news",
      "claim": "",
      "claim_date": "YYYY-MM-DD",
      "source_url": "",
      "source_name": "",
      "numeric_values": {},
      "why_relevant": ""
    }
  ],
  "collection_notes": {
    "queries_used": [],
    "missing_categories": []
  }
}
```

실행:
```bash
GEMINI_CLI_TRUST_WORKSPACE=true ~/.local/bin/gemini --prompt "$(cat /Volumes/AI/claude/gemini_evidence_{TICKER}.md)" > /Volumes/AI/reviews/{TICKER}/evidence_raw.json 2>/dev/null
```

저장:
`./reviews/{TICKER}/evidence_raw.json`

---

### STEP 3 — Claude: Evidence Validation

Claude는 금융 evidence 검증자다.

`./reviews/{TICKER}/evidence_raw.json`의 모든 claim에 대해 URL, 날짜, 수치, 문맥 일치 여부를 검증한다.

**STRICT RULES**

- unsupported claim 거부
- stale evidence 거부
- speculative reasoning 거부
- numerical consistency 검증
- claim과 source 내용 불일치 시 CONTRADICTED 처리
- JSON only

**검증 프로세스**

1. 각 claim의 source URL에 직접 접속한다.
2. claim 내용이 source에 의해 직접 뒷받침되는지 확인한다.
3. 날짜가 stale 기준을 넘었는지 확인한다.
4. 수치가 원문과 일치하는지 확인한다.
5. claim별 status를 부여한다.

**분류 기준**

| 결과 | 의미 |
|------|------|
| VERIFIED | 출처가 claim을 직접적으로 뒷받침 |
| PARTIALLY_VERIFIED | 일부 내용만 확인 가능 |
| STALE | 데이터 유형별 유효기간 초과 |
| UNSUPPORTED | 출처 없음 또는 검증 불가 |
| CONTRADICTED | 출처 내용과 claim이 불일치 |

**data_quality 판정**

| data_quality | 기준 |
|--------------|------|
| GOOD | VERIFIED + PARTIALLY_VERIFIED 비율 70% 이상, CONTRADICTED 없음 |
| MARGINAL | VERIFIED + PARTIALLY_VERIFIED 비율 40~69% |
| POOR | VERIFIED + PARTIALLY_VERIFIED 비율 40% 미만 또는 CONTRADICTED 다수 |

**출력 JSON 형식**

```json
{
  "ticker": "{TICKER}",
  "as_of": "YYYY-MM-DD",
  "validation_summary": {
    "total_claims": 0,
    "verified": 0,
    "partially_verified": 0,
    "stale": 0,
    "unsupported": 0,
    "contradicted": 0,
    "data_quality": "GOOD | MARGINAL | POOR"
  },
  "validated_claims": [
    {
      "id": "",
      "category": "",
      "status": "VERIFIED | PARTIALLY_VERIFIED",
      "claim": "",
      "claim_date": "YYYY-MM-DD",
      "source_url": "",
      "source_name": "",
      "numeric_values": {},
      "validation_note": ""
    }
  ],
  "excluded_claims": [
    {
      "id": "",
      "category": "",
      "status": "STALE | UNSUPPORTED | CONTRADICTED",
      "claim": "",
      "reason": ""
    }
  ]
}
```

저장:
`./reviews/{TICKER}/evidence_validated.json`

---

### STEP 4 — Python: Historical Feature Distribution Lite

Python은 통계 계산 엔진이다.

현재 feature 조합과 유사했던 과거 구간을 찾아 5일, 10일, 20일 forward return 분포를 계산한다.
이 단계는 로컬 계산만 수행하며, AI API를 사용하지 않는다.

**STRICT RULES**

- Python으로 계산한다
- 과거 OHLCV 원본을 LLM에게 넣어 통계 계산시키지 않는다
- 주관적 차트 유사성 검색 금지
- guessed probability 금지
- sample_size가 부족하면 확률 근거로 사용하지 않는다
- look-ahead bias 금지
- 현재 날짜 이후 데이터 사용 금지
- JSON only

**입력 파일**

- `./reviews/{TICKER}/ohlcv_daily.csv`
- `./reviews/{TICKER}/benchmark_ohlcv_daily.csv`
- `./reviews/{TICKER}/market_features.json`

**필수 계산**

1. RSI 14 bucket
2. EMA20 distance bucket
3. EMA50 distance bucket
4. Volume expansion bucket
5. Relative strength 20d bucket
6. Matched historical sample size
7. Future 5-day return distribution
8. Future 10-day return distribution
9. Future 20-day return distribution
10. Hit rate
11. Average return
12. Median return
13. Downside deviation
14. Tail risk p5/p10
15. Max favorable excursion
16. Max adverse excursion

**Feature bucket 정의**

| feature | bucket |
|---------|--------|
| RSI 14 | `<30`, `30_45`, `45_55`, `55_70`, `>=70` |
| EMA distance | `<-5pct`, `-5_0pct`, `0_5pct`, `>=5pct` |
| Volume expansion | `<0.8x`, `0.8_1.2x`, `1.2_1.5x`, `>=1.5x` |
| Relative strength 20d | `<-5pct`, `-5_0pct`, `0_5pct`, `>=5pct` |

**Python 스크립트 생성**

`./scripts/feature_distribution_lite.py`가 없으면 아래 스크립트를 생성한다. 이미 있으면 사용자 수정 여부를 확인하지 말고 기존 파일을 읽은 뒤, 목적이 같으면 재사용한다.

```python
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


HORIZONS = [5, 10, 20]


def pct(x):
    if pd.isna(x):
        return None
    return round(float(x) * 100.0, 4)


def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bucket_rsi(value):
    if pd.isna(value):
        return None
    if value < 30:
        return "<30"
    if value < 45:
        return "30_45"
    if value < 55:
        return "45_55"
    if value < 70:
        return "55_70"
    return ">=70"


def bucket_pct(value):
    if pd.isna(value):
        return None
    if value < -0.05:
        return "<-5pct"
    if value < 0:
        return "-5_0pct"
    if value < 0.05:
        return "0_5pct"
    return ">=5pct"


def bucket_volume(value):
    if pd.isna(value):
        return None
    if value < 0.8:
        return "<0.8x"
    if value < 1.2:
        return "0.8_1.2x"
    if value < 1.5:
        return "1.2_1.5x"
    return ">=1.5x"


def load_ohlcv(path):
    df = pd.read_csv(path)
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    df = df[required].copy()
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")
    return df.reset_index(drop=True)


def add_features(df, benchmark=None):
    out = df.copy()
    out["rsi_14"] = rsi(out["close"], 14)
    out["ema_20"] = out["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    out["ema_50"] = out["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    out["ema20_distance"] = out["close"] / out["ema_20"] - 1
    out["ema50_distance"] = out["close"] / out["ema_50"] - 1
    out["volume_avg_20"] = out["volume"].rolling(20, min_periods=20).mean()
    out["volume_expansion"] = out["volume"] / out["volume_avg_20"]
    out["return_20d"] = out["close"].pct_change(20)

    if benchmark is not None and not benchmark.empty:
        bench = benchmark[["date", "close"]].rename(columns={"close": "benchmark_close"}).copy()
        bench["benchmark_return_20d"] = bench["benchmark_close"].pct_change(20)
        out = out.merge(bench[["date", "benchmark_return_20d"]], on="date", how="left")
        out["relative_strength_20d"] = out["return_20d"] - out["benchmark_return_20d"]
    else:
        out["benchmark_return_20d"] = np.nan
        out["relative_strength_20d"] = np.nan

    out["rsi_bucket"] = out["rsi_14"].apply(bucket_rsi)
    out["ema20_distance_bucket"] = out["ema20_distance"].apply(bucket_pct)
    out["ema50_distance_bucket"] = out["ema50_distance"].apply(bucket_pct)
    out["volume_expansion_bucket"] = out["volume_expansion"].apply(bucket_volume)
    out["relative_strength_bucket"] = out["relative_strength_20d"].apply(bucket_pct)

    for horizon in HORIZONS:
        out[f"fwd_return_{horizon}d"] = out["close"].shift(-horizon) / out["close"] - 1
        future_highs = [out["high"].shift(-i) for i in range(1, horizon + 1)]
        future_lows = [out["low"].shift(-i) for i in range(1, horizon + 1)]
        out[f"mfe_{horizon}d"] = pd.concat(future_highs, axis=1).max(axis=1) / out["close"] - 1
        out[f"mae_{horizon}d"] = pd.concat(future_lows, axis=1).min(axis=1) / out["close"] - 1
    return out


def describe_returns(rows, horizon):
    returns = rows[f"fwd_return_{horizon}d"].dropna()
    mfe = rows[f"mfe_{horizon}d"].dropna()
    mae = rows[f"mae_{horizon}d"].dropna()
    if returns.empty:
        return {
            "sample_size": 0,
            "hit_rate_positive": None,
            "average_return_pct": None,
            "median_return_pct": None,
            "p5_return_pct": None,
            "p10_return_pct": None,
            "p25_return_pct": None,
            "p75_return_pct": None,
            "p90_return_pct": None,
            "downside_deviation_pct": None,
            "median_mfe_pct": None,
            "median_mae_pct": None,
            "worst_mae_pct": None
        }

    downside = returns[returns < 0]
    downside_dev = downside.std(ddof=0) if len(downside) else 0.0
    return {
        "sample_size": int(len(returns)),
        "hit_rate_positive": round(float((returns > 0).mean()), 4),
        "average_return_pct": pct(returns.mean()),
        "median_return_pct": pct(returns.median()),
        "p5_return_pct": pct(returns.quantile(0.05)),
        "p10_return_pct": pct(returns.quantile(0.10)),
        "p25_return_pct": pct(returns.quantile(0.25)),
        "p75_return_pct": pct(returns.quantile(0.75)),
        "p90_return_pct": pct(returns.quantile(0.90)),
        "downside_deviation_pct": pct(downside_dev),
        "median_mfe_pct": pct(mfe.median()) if not mfe.empty else None,
        "median_mae_pct": pct(mae.median()) if not mae.empty else None,
        "worst_mae_pct": pct(mae.min()) if not mae.empty else None
    }


def sample_quality(sample_size):
    if sample_size < 50:
        return "INSUFFICIENT_SAMPLE"
    if sample_size < 100:
        return "REFERENCE_ONLY"
    return "USABLE_AS_ANCHOR"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--ohlcv", required=True)
    parser.add_argument("--benchmark-ohlcv")
    parser.add_argument("--market-features", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        df = load_ohlcv(args.ohlcv)
        benchmark = load_ohlcv(args.benchmark_ohlcv) if args.benchmark_ohlcv else None
        features = add_features(df, benchmark)
        usable = features.dropna(subset=[
            "rsi_bucket",
            "ema20_distance_bucket",
            "volume_expansion_bucket"
        ]).copy()

        if usable.empty or len(usable) < 80:
            result = {
                "ticker": args.ticker,
                "status": "DATA_MISSING",
                "reason": "Not enough historical rows with calculated features.",
                "sample_policy": sample_quality(0),
                "selected_tier": None,
                "current_feature_state": {},
                "tiers": []
            }
            output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            return

        current = usable.iloc[-1]
        historical = usable.iloc[:-max(HORIZONS)].copy()

        tiers = [
            ("A_exact", ["rsi_bucket", "ema20_distance_bucket", "volume_expansion_bucket", "relative_strength_bucket"]),
            ("B_drop_volume", ["rsi_bucket", "ema20_distance_bucket", "relative_strength_bucket"]),
            ("C_rsi_rs_only", ["rsi_bucket", "relative_strength_bucket"]),
            ("D_rsi_ema_only", ["rsi_bucket", "ema20_distance_bucket"])
        ]

        tier_results = []
        selected = None

        for tier_name, cols in tiers:
            cols = [col for col in cols if pd.notna(current.get(col))]
            if not cols:
                continue
            mask = pd.Series(True, index=historical.index)
            for col in cols:
                mask &= historical[col] == current[col]
            matched = historical[mask].copy()
            sample_size = int(len(matched))
            distributions = {
                f"{horizon}d": describe_returns(matched, horizon)
                for horizon in HORIZONS
            }
            tier_result = {
                "tier": tier_name,
                "matched_features": cols,
                "sample_size": sample_size,
                "sample_policy": sample_quality(sample_size),
                "distributions": distributions
            }
            tier_results.append(tier_result)
            if selected is None and sample_size >= 50:
                selected = tier_result

        if selected is None and tier_results:
            selected = max(tier_results, key=lambda item: item["sample_size"])

        selected_sample = selected["sample_size"] if selected else 0
        policy = sample_quality(selected_sample)
        statistical_use = "DISALLOWED" if selected_sample < 50 else ("REFERENCE_ONLY" if selected_sample < 100 else "ANCHOR_ALLOWED")

        current_feature_state = {
            "date": str(current["date"].date()),
            "close": round(float(current["close"]), 4),
            "rsi_14": round(float(current["rsi_14"]), 4) if pd.notna(current["rsi_14"]) else None,
            "rsi_bucket": current.get("rsi_bucket"),
            "ema20_distance_pct": pct(current.get("ema20_distance")),
            "ema20_distance_bucket": current.get("ema20_distance_bucket"),
            "ema50_distance_pct": pct(current.get("ema50_distance")),
            "ema50_distance_bucket": current.get("ema50_distance_bucket"),
            "volume_expansion": round(float(current["volume_expansion"]), 4) if pd.notna(current["volume_expansion"]) else None,
            "volume_expansion_bucket": current.get("volume_expansion_bucket"),
            "relative_strength_20d_pct": pct(current.get("relative_strength_20d")),
            "relative_strength_bucket": current.get("relative_strength_bucket")
        }

        result = {
            "ticker": args.ticker,
            "status": "OK",
            "calculation_engine": "local_python",
            "api_usage": "none_for_this_step",
            "input_files": {
                "ohlcv": args.ohlcv,
                "benchmark_ohlcv": args.benchmark_ohlcv,
                "market_features": args.market_features
            },
            "current_feature_state": current_feature_state,
            "selected_tier": selected["tier"] if selected else None,
            "selected_sample_size": selected_sample,
            "sample_policy": policy,
            "statistical_use": statistical_use,
            "selected_distribution": selected["distributions"] if selected else {},
            "all_tiers": tier_results,
            "guardrails": {
                "sample_size_lt_50": "Do not use as probability evidence.",
                "sample_size_50_99": "Reference only. Max scenario weight 0.15.",
                "sample_size_gte_100": "Can be used as statistical anchor. Max scenario weight 0.35."
            }
        }
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        result = {
            "ticker": args.ticker,
            "status": "ERROR",
            "error": str(exc),
            "sample_policy": "INSUFFICIENT_SAMPLE",
            "statistical_use": "DISALLOWED"
        }
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

**실행**

실행 전 `pandas`, `numpy` 의존성을 확인한다.
의존성이 없으면 자동 설치하지 말고 `feature_distribution_lite.json`에 `DEPENDENCY_MISSING` 오류를 기록한 뒤 STEP 5로 진행한다.

```bash
python3 - <<'PY'
import importlib.util
import json
from pathlib import Path

missing = [name for name in ("numpy", "pandas") if importlib.util.find_spec(name) is None]
if missing:
    out = Path("./reviews/{TICKER}/feature_distribution_lite.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "ticker": "{TICKER}",
        "status": "ERROR",
        "error": "DEPENDENCY_MISSING",
        "missing_dependencies": missing,
        "sample_policy": "INSUFFICIENT_SAMPLE",
        "statistical_use": "DISALLOWED"
    }, ensure_ascii=False, indent=2))
    raise SystemExit(2)
PY

if [ $? -eq 0 ]; then
  python3 ./scripts/feature_distribution_lite.py \
    --ticker {TICKER} \
    --ohlcv ./reviews/{TICKER}/ohlcv_daily.csv \
    --benchmark-ohlcv ./reviews/{TICKER}/benchmark_ohlcv_daily.csv \
    --market-features ./reviews/{TICKER}/market_features.json \
    --output ./reviews/{TICKER}/feature_distribution_lite.json
fi
```

저장:
`./reviews/{TICKER}/feature_distribution_lite.json`

---

### STEP 5 — GPT: Probabilistic Scenario Generation

GPT는 확률적 시장 추론 엔진이다.

검증된 evidence, market features, Python feature distribution만 사용해 bullish, neutral, bearish 세 가지 시나리오를 생성한다.

다음 프롬프트를 `./claude/gpt_scenario_{TICKER}.md`에 저장한다.

```
You are a probabilistic market reasoning engine.

Input files:
- ./reviews/{TICKER}/market_features.json
- ./reviews/{TICKER}/evidence_validated.json
- ./reviews/{TICKER}/feature_distribution_lite.json

Your task:
Generate balanced bullish, neutral, and bearish scenarios using ONLY verified evidence, structured market features, and local Python statistical distribution results.

STRICT RULES:
- No certainty language
- No emotional hype
- No unsupported claims
- Explicitly state uncertainty
- Probabilities must sum to 100%
- Neutral/base scenario is mandatory
- Do not generate buy/sell/hold recommendation
- Do not generate entry price, stop loss, or position sizing
- If data_quality is POOR, scenario confidence must be LOW
- Use only VERIFIED and PARTIALLY_VERIFIED evidence
- Exclude STALE, UNSUPPORTED, and CONTRADICTED claims
- Do not invent probabilities when feature_distribution_lite has insufficient sample
- If selected_sample_size < 50, statistical_distribution_weight must be 0
- If selected_sample_size is 50~99, statistical_distribution_weight must be <= 0.15
- If selected_sample_size >= 100, statistical_distribution_weight must be <= 0.35
- Output JSON only

Requirements:
1. Generate bullish scenario
2. Generate neutral/base scenario
3. Generate bearish scenario
4. Assign estimated probability
5. Define invalidation condition
6. Define time horizon
7. Estimate expected move range
8. Provide p10 / p50 / p90 expected return
9. State key uncertainty
10. Include statistical_distribution_reference
11. Include base rate reference

Output schema:
{
  "ticker": "{TICKER}",
  "as_of": "YYYY-MM-DD",
  "time_horizon": {
    "type": "swing",
    "trading_days": 10,
    "target_date": "YYYY-MM-DD"
  },
  "reference_price": 0.0,
  "data_quality": "GOOD | MARGINAL | POOR",
  "statistical_distribution_reference": {
    "status": "OK | DATA_MISSING | ERROR",
    "selected_tier": "",
    "selected_sample_size": 0,
    "sample_policy": "INSUFFICIENT_SAMPLE | REFERENCE_ONLY | USABLE_AS_ANCHOR",
    "statistical_distribution_weight": 0.0,
    "used_in_probability": false,
    "reason": ""
  },
  "base_rate_reference": {
    "market_regime": "",
    "sector_regime": "",
    "historical_forward_window": "10 trading days",
    "note": "Base rate is approximate and should be validated over time."
  },
  "scenarios": [
    {
      "type": "bullish",
      "probability": 0.0,
      "expected_move_pct": {
        "p10": 0.0,
        "p50": 0.0,
        "p90": 0.0
      },
      "supporting_evidence_ids": [],
      "market_feature_ids": [],
      "statistical_support": {
        "horizon": "10d",
        "hit_rate_positive": null,
        "median_return_pct": null,
        "sample_size": 0
      },
      "invalidation_condition": "",
      "key_uncertainty": ""
    },
    {
      "type": "neutral",
      "probability": 0.0,
      "expected_move_pct": {
        "p10": 0.0,
        "p50": 0.0,
        "p90": 0.0
      },
      "supporting_evidence_ids": [],
      "market_feature_ids": [],
      "statistical_support": {
        "horizon": "10d",
        "hit_rate_positive": null,
        "median_return_pct": null,
        "sample_size": 0
      },
      "invalidation_condition": "",
      "key_uncertainty": ""
    },
    {
      "type": "bearish",
      "probability": 0.0,
      "expected_move_pct": {
        "p10": 0.0,
        "p50": 0.0,
        "p90": 0.0
      },
      "supporting_evidence_ids": [],
      "market_feature_ids": [],
      "statistical_support": {
        "horizon": "10d",
        "hit_rate_positive": null,
        "median_return_pct": null,
        "sample_size": 0
      },
      "invalidation_condition": "",
      "key_uncertainty": ""
    }
  ],
  "expected_move_distribution": {
    "p10": 0.0,
    "p50": 0.0,
    "p90": 0.0
  },
  "confidence": {
    "level": "LOW | MEDIUM | HIGH",
    "score": 0.0,
    "reason": ""
  }
}
```

실행:
```bash
npx @openai/codex exec --dangerously-bypass-approvals-and-sandbox -s danger-full-access -C /Volumes/AI "$(cat ./claude/gpt_scenario_{TICKER}.md)" > ./reviews/{TICKER}/scenario_forecast.json
```

저장:
`./reviews/{TICKER}/scenario_forecast.json`

---

### STEP 6 — Claude: Final Review

Claude는 최종 예측 리뷰 작성자다.

다음 4개 파일을 읽는다:

- `./reviews/{TICKER}/market_features.json`
- `./reviews/{TICKER}/evidence_validated.json`
- `./reviews/{TICKER}/feature_distribution_lite.json`
- `./reviews/{TICKER}/scenario_forecast.json`

중요:
이 단계에서도 매수/매도 추천을 생성하지 않는다.

**필수 섹션**

1. 핵심 요약
2. 데이터 품질
3. 측정된 market feature 요약
4. Python historical feature distribution 요약
5. 통계 표본 수 및 사용 가능 여부
6. 검증된 핵심 evidence
7. 제외된 evidence
8. Bullish scenario
9. Neutral/base scenario
10. Bearish scenario
11. 확률 및 예상 변동폭 요약
12. 주요 uncertainty
13. 사후 검증을 위해 기록할 항목
14. 결론 3문장 이내

**통계 해석 규칙**

- `sample_size < 50`이면 "통계 표본 부족"이라고 명시한다.
- `sample_size 50~99`이면 "참고용"이라고 명시한다.
- `sample_size >= 100`이면 "보조 anchor로 사용 가능"이라고 명시한다.
- 통계 분포와 evidence가 충돌하면 confidence를 높이지 않는다.

저장:
`./reviews/{TICKER}/final_review.md`

---

### STEP 7 — Prediction Logging & Simple Validation

Claude는 prediction tracking engine이다.

이번 예측을 구조화된 JSON으로 저장하고, 향후 target horizon이 지난 뒤 실제 결과와 비교할 수 있도록 기록한다.

**기록 항목**

1. Prediction date
2. Ticker
3. Time horizon
4. Scenario probabilities
5. Expected move p10/p50/p90
6. Feature distribution sample size
7. Feature distribution selected tier
8. Actual move after target horizon
9. Direction hit
10. Magnitude error
11. Max favorable excursion
12. Max adverse excursion
13. Brier score
14. Calibration bucket
15. Prediction success/failure

**Prediction Record JSON 형식**

```json
{
  "prediction": {
    "ticker": "{TICKER}",
    "prediction_date": "YYYY-MM-DD",
    "target_date": "YYYY-MM-DD",
    "horizon_trading_days": 10,
    "reference_price": 0.0,
    "data_quality": "GOOD | MARGINAL | POOR",
    "confidence": 0.0,
    "feature_distribution": {
      "status": "OK | DATA_MISSING | ERROR",
      "selected_tier": "",
      "selected_sample_size": 0,
      "sample_policy": "INSUFFICIENT_SAMPLE | REFERENCE_ONLY | USABLE_AS_ANCHOR",
      "statistical_use": "DISALLOWED | REFERENCE_ONLY | ANCHOR_ALLOWED"
    },
    "scenarios": {
      "bullish": {
        "probability": 0.0,
        "expected_move_pct_p50": 0.0
      },
      "neutral": {
        "probability": 0.0,
        "expected_move_pct_p50": 0.0
      },
      "bearish": {
        "probability": 0.0,
        "expected_move_pct_p50": 0.0
      }
    },
    "primary_scenario": "bullish | neutral | bearish",
    "expected_move_distribution": {
      "p10": 0.0,
      "p50": 0.0,
      "p90": 0.0
    },
    "validation": {
      "actual_close_on_target_date": null,
      "actual_move_pct": null,
      "realized_scenario": null,
      "direction_hit": null,
      "magnitude_error": null,
      "max_favorable_excursion": null,
      "max_adverse_excursion": null,
      "brier_score": null,
      "calibration_bucket": "",
      "success": null
    }
  }
}
```

저장:

- `./reviews/{TICKER}/prediction_record.json`
- `./logs/predictions/{TICKER}_{YYYYMMDD}.json`

`./logs/prediction_log.md`에도 추가한다. 기존 내용은 보존한다.

```markdown
---
## {TICKER} | {날짜} | 예측 기록
- 기준가: {reference_price}
- target date: {target_date}
- horizon: {horizon_trading_days} trading days
- data_quality: {data_quality}
- confidence: {confidence}
- primary scenario: {primary_scenario}
- scenario probabilities: Bullish {bullish_probability}% / Neutral {neutral_probability}% / Bearish {bearish_probability}%
- expected move p10/p50/p90: {p10}% / {p50}% / {p90}%
- feature distribution: {selected_tier}, sample_size {selected_sample_size}, {sample_policy}
- 실제 결과: [미기록]
- direction hit: [미기록]
- magnitude error: [미기록]
- brier score: [미기록]
```

---

## Lightweight Validation

30~50개 예측이 쌓일 때마다 `./logs/validation_summary.md`를 업데이트한다.

검증 항목:

1. Overall hit rate
2. Direction hit rate
3. Average magnitude error
4. Brier score
5. Calibration by confidence bucket
6. Overconfidence detection
7. Persistent failure patterns
8. Ticker별 성능 편차
9. Market regime별 성능 편차
10. Data quality별 성능 편차
11. Feature distribution sample_size별 성능 편차
12. Feature distribution selected_tier별 성능 편차

### Calibration Bucket 예시

| 예측 confidence | 실제 성공률 | 해석 |
|-----------------|------------:|------|
| 50~60% | 54% | 적정 |
| 60~70% | 51% | 과신 가능 |
| 70~80% | 58% | 과신 |
| 80%+ | 55% | 심각한 과신 |

---

## Recommended Operation

권장 사용 방식:

- Daily analysis
- Pre-market 또는 after market close
- Swing trading horizon
- 5~20 trading day outlook
- 초기 ticker 수: 3~5개
- 최소 30개 예측 전까지 매매 자동화 금지
- 최소 100개 예측 전까지 position sizing 모델 연결 금지
- feature distribution은 처음에는 참고용으로만 사용
- sample_size와 실제 성능이 쌓인 뒤에만 가중치를 높인다

---

## Realistic Expectation

이 시스템은 다음을 목표로 한다:

- practical
- explainable
- maintainable
- measurable
- experimentally useful
- lightweight statistical validation

이 시스템은 다음이 아니다:

- guaranteed alpha
- fully automated hedge fund system
- oracle
- standalone trading bot
- execution engine
- institutional quant platform

Primary goal:

검증 가능한 예측을 반복적으로 생성하고, 시간이 지날수록 예측 품질과 feature distribution의 유용성을 측정 및 개선하는 것이다.

---

## 완료 보고

파이프라인 종료 후 콘솔에 출력:

- 생성 파일 목록
- data_quality
- feature distribution status
- selected tier + sample size + sample policy
- scenario probabilities
- primary scenario
- expected move p10/p50/p90
- confidence
- 검증된 evidence 수
- 제외된 evidence 수
- prediction log 저장 경로

---

## 요약

| 단계 | 담당 | 핵심 역할 |
|------|------|-----------|
| STEP 1 | Claude | TradingView MCP 기반 market feature 및 OHLCV 추출 |
| STEP 2 | Gemini | factual evidence 수집 |
| STEP 3 | Claude | evidence 검증 및 stale 제거 |
| STEP 4 | Python | RSI/EMA/거래량/상대강도 기반 historical feature distribution 계산 |
| STEP 5 | GPT | 통계 분포와 검증 evidence를 반영한 확률 시나리오 생성 |
| STEP 6 | Claude | 최종 예측 리뷰 작성 |
| STEP 7 | Claude | prediction logging 및 검증 준비 |
