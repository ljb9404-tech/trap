# stock-review v2

**목적:** 자동매매 실행 전 단계에서 사용하는 경량 AI 기반 주식 예측 연구 파이프라인  
**사용법:** `/stock-review_v2 TICKER`  
**예시:** `/stock-review_v2 PLTR`, `/stock-review_v2 NVDA`, `/stock-review_v2 005930`  

---

## 핵심 원칙

이 파이프라인은 매매 주문이나 자동매매 신호를 생성하지 않는다.
목적은 예측 가능한 형태의 시장 가설을 만들고, 시간이 지나면 실제 결과와 비교할 수 있도록 기록하는 것이다.

**AI는 예언자가 아니라 추론 보조 도구다.**
좋은 분석은 수익을 보장하지 않는다.
일관된 기록과 검증이 복잡한 예측보다 중요하다.

### 목표

- 측정 가능한 시장 feature 추출
- 근거 기반 기업/섹터/매크로 evidence 수집
- 출처 검증 및 stale 데이터 제거
- bullish / neutral / bearish 확률 시나리오 생성
- 예측 로그 축적
- 30~50개 예측마다 성능 검증

### 공통 규칙

- 매수/매도 추천 금지
- 자동 주문, 진입가, 손절가, 포지션 사이징 생성 금지
- 방향성 표현은 STEP 4 확률 시나리오에서만 허용
- 검증되지 않은 정보는 예측에 반영하지 않는다
- 모든 수치에는 날짜와 출처를 남긴다
- 모든 시나리오 확률 합계는 100%여야 한다
- neutral/base scenario를 반드시 포함한다
- JSON 산출물이 필요한 단계는 JSON only를 지킨다

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

---

## 파일 경로 규칙

모든 파일은 티커별 디렉토리에 저장한다. 여러 종목 동시 실행 시 충돌을 피한다.

```
./reports/{ticker}.md                         ← 사람이 읽는 요약 보고서
./reviews/{TICKER}/market_features.json       ← TradingView feature 추출
./reviews/{TICKER}/evidence_raw.json          ← Gemini evidence 원본 수집
./reviews/{TICKER}/evidence_validated.json    ← Claude evidence 검증 결과
./reviews/{TICKER}/scenario_forecast.json     ← GPT 확률 시나리오
./reviews/{TICKER}/prediction_record.json     ← 단일 예측 기록
./reviews/{TICKER}/final_review.md            ← 최종 예측 리뷰
./logs/predictions/{TICKER}_{YYYYMMDD}.json   ← 누적 검증용 예측 로그
./logs/prediction_log.md                      ← 사람이 읽는 예측 로그
./logs/validation_summary.md                  ← 30~50개 단위 검증 요약
```

---

## 파이프라인 (6단계)

`$ARGUMENTS`에서 티커를 추출한다. 없으면 사용자에게 묻는다.
이하 `{TICKER}` = 대문자, `{ticker}` = 소문자.

디렉토리 생성:
```bash
mkdir -p ./reports ./reviews/{TICKER} ./logs/predictions
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

**출력 JSON 형식**

```json
{
  "ticker": "{TICKER}",
  "as_of": "YYYY-MM-DD",
  "source": "TradingView MCP",
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
    "vs_spy_20d_pct": 0.0,
    "vs_sector_20d_pct": 0.0
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

### STEP 4 — GPT: Probabilistic Scenario Generation

GPT는 확률적 시장 추론 엔진이다.

검증된 evidence와 market features만 사용해 bullish, neutral, bearish 세 가지 시나리오를 생성한다.

다음 프롬프트를 `./claude/gpt_scenario_{TICKER}.md`에 저장한다.

```
You are a probabilistic market reasoning engine.

Input files:
- ./reviews/{TICKER}/market_features.json
- ./reviews/{TICKER}/evidence_validated.json

Your task:
Generate balanced bullish, neutral, and bearish scenarios using ONLY verified evidence and structured market features.

STRICT RULES:
- No certainty language
- No emotional hype
- No unsupported claims
- Explicitly state uncertainty
- Use probability estimates conservatively
- Probabilities must sum to 100%
- Neutral/base scenario is mandatory
- Do not generate buy/sell/hold recommendation
- Do not generate entry price, stop loss, or position sizing
- If data_quality is POOR, scenario confidence must be LOW
- Use only VERIFIED and PARTIALLY_VERIFIED evidence
- Exclude STALE, UNSUPPORTED, and CONTRADICTED claims
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
10. Include base rate reference

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

### STEP 5 — Claude: Final Review

Claude는 최종 예측 리뷰 작성자다.

다음 3개 파일을 읽는다:

- `./reviews/{TICKER}/market_features.json`
- `./reviews/{TICKER}/evidence_validated.json`
- `./reviews/{TICKER}/scenario_forecast.json`

중요:
이 단계에서도 매수/매도 추천을 생성하지 않는다.

**필수 섹션**

1. 핵심 요약
2. 데이터 품질
3. 측정된 market feature 요약
4. 검증된 핵심 evidence
5. 제외된 evidence
6. Bullish scenario
7. Neutral/base scenario
8. Bearish scenario
9. 확률 및 예상 변동폭 요약
10. 주요 uncertainty
11. 사후 검증을 위해 기록할 항목
12. 결론 3문장 이내

저장:
`./reviews/{TICKER}/final_review.md`

---

### STEP 6 — Prediction Logging & Simple Validation

Claude는 prediction tracking engine이다.

이번 예측을 구조화된 JSON으로 저장하고, 향후 target horizon이 지난 뒤 실제 결과와 비교할 수 있도록 기록한다.

**기록 항목**

1. Prediction date
2. Ticker
3. Time horizon
4. Scenario probabilities
5. Expected move p10/p50/p90
6. Actual move after target horizon
7. Direction hit
8. Magnitude error
9. Max favorable excursion
10. Max adverse excursion
11. Brier score
12. Calibration bucket
13. Prediction success/failure

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

---

## Realistic Expectation

이 시스템은 다음을 목표로 한다:

- practical
- explainable
- maintainable
- measurable
- experimentally useful

이 시스템은 다음이 아니다:

- guaranteed alpha
- fully automated hedge fund system
- oracle
- standalone trading bot
- execution engine

Primary goal:

검증 가능한 예측을 반복적으로 생성하고, 시간이 지날수록 예측 품질을 측정 및 개선하는 것이다.

---

## 완료 보고

파이프라인 종료 후 콘솔에 출력:

- 생성 파일 목록
- data_quality
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
| STEP 1 | Claude | TradingView MCP 기반 market feature 추출 |
| STEP 2 | Gemini | factual evidence 수집 |
| STEP 3 | Claude | evidence 검증 및 stale 제거 |
| STEP 4 | GPT | 확률 시나리오 생성 |
| STEP 5 | Claude | 최종 예측 리뷰 작성 |
| STEP 6 | Claude | prediction logging 및 검증 준비 |
