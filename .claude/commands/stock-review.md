# stock-review

**목적:** 자동매매 신호 생성을 위한 고신뢰도 주식 분석 파이프라인  
**사용법:** `/stock-review TICKER`  
**예시:** `/stock-review PLTR`, `/stock-review NVDA`, `/stock-review 005930`

---

## 핵심 원칙

이 파이프라인은 실제 돈이 걸린 자동매매 시스템의 입력값을 만든다.
**신뢰할 수 없는 데이터는 쓰지 않는다. 검증된 사실만 최종 판단에 반영한다.**

### 데이터 신뢰도 등급
- **VERIFIED**: URL 접속 또는 TradingView 수치로 직접 확인됨
- **REPORTED**: 신뢰할 수 있는 매체에서 인용됐으나 원문 미확인
- **UNVERIFIED**: 출처 불명 또는 접속 불가 — 가중치 0으로 처리, 최종 판단 제외
- **ESTIMATED**: 추정값, 반드시 "~" 접두어 표기

### 공통 규칙
- 수치 없는 주장 금지
- UNVERIFIED 인용이 전체 50% 초과 시 → `data_quality: POOR` → 매매 신호 `NO_ACTION` 강제
- 모든 시나리오 확률 합계 = 100% 필수

---

## 파일 경로 규칙

모든 파일은 티커별 디렉토리에 저장한다. 여러 종목 동시 실행 시 충돌 없음.

```
./reports/{ticker}.md                        ← 기술적 분석
./reviews/{TICKER}/bull_search.md            ← Gemini Bull 리서치
./reviews/{TICKER}/bear_search.md            ← Gemini Bear 리서치
./reviews/{TICKER}/verified_facts.md         ← Claude 검증 결과
./reviews/{TICKER}/gpt_scoring.md            ← GPT 채점
./reviews/{TICKER}/final_review.md           ← 최종 통합 리뷰
./logs/signals/{TICKER}_{YYYYMMDD}.json      ← 자동매매 신호
./logs/prediction_log.md                     ← 백테스팅 로그
```

---

## 파이프라인 (7단계)

`$ARGUMENTS`에서 티커를 추출한다. 없으면 사용자에게 묻는다.
이하 `{TICKER}` = 대문자, `{ticker}` = 소문자.

디렉토리 생성:
```bash
mkdir -p ./reviews/{TICKER} ./logs/signals
```

---

### STEP 1 — Claude: TradingView 기술적 분석 + 기초 데이터 수집

TradingView MCP로 실시간 데이터를 읽는다.

**수집 항목 (미확인 시 null, 추정 시 ~ 접두어):**

| 항목 | 소스 | 신뢰도 |
|------|------|--------|
| 현재가, OHLCV | TradingView quote_get | VERIFIED |
| RSI, MACD, EMA | TradingView data_get_study_values | VERIFIED |
| 100일 고/저가 | TradingView data_get_ohlcv | VERIFIED |
| 지지/저항 레벨 | TradingView 차트 | VERIFIED |
| 애널리스트 컨센서스 | TradingView symbol_info | VERIFIED |
| 목표주가 | TradingView + WebSearch | REPORTED |
| 최근 실적 | WebSearch | REPORTED |
| 섹터 비교 | WebSearch | REPORTED |

**보고서 포함 섹션:**
1. 핵심 요약 (현재가, 거래량, 100일 고/저가, RSI, MACD, 컨센서스, 목표주가)
2. 추세 분석 (100일 중기 + 5거래일 단기 일봉 테이블)
3. 거래량 분석 (평균 대비 현재 거래량, 이상 급증 여부)
4. 기술적 지표 (RSI 과매수/과매도, MACD 다이버전스, 골든/데드크로스)
5. 펀더멘털 (PER, PBR, EPS 성장률, 업종 대비 밸류에이션)
6. 월가 컨센서스 (애널리스트 목표주가 테이블: 기관명, 의견, 목표가, 날짜)
7. 매크로 시황 (Fed 금리, 환율, 섹터 흐름, 지정학적 이슈)
8. 초기 시나리오 (Bull/Base/Bear, 각 확률 + 목표가)
9. 기대값(EV) 계산

보고서 맨 하단에 다음 JSON을 포함한다:

```json
{
  "ticker": "",
  "as_of": "",
  "price": 0.0,
  "data_quality": "GOOD | MARGINAL | POOR",
  "technical": {
    "rsi": 0.0,
    "macd_signal": "BULLISH | BEARISH | NEUTRAL",
    "trend": "BULLISH | BEARISH | SIDEWAYS",
    "support": [],
    "resistance": [],
    "volume_vs_avg": 0.0
  },
  "fundamental": {
    "per": 0.0,
    "pbr": 0.0,
    "eps_growth_yoy": 0.0,
    "sector_per_avg": 0.0
  },
  "macro": {
    "fed_rate": 0.0,
    "usd_krw": 0.0,
    "sector_momentum": "POSITIVE | NEGATIVE | NEUTRAL"
  },
  "scenarios": [
    { "name": "Bull", "probability": 0.0, "target": 0.0, "trigger": "" },
    { "name": "Base", "probability": 0.0, "target": 0.0, "trigger": "" },
    { "name": "Bear", "probability": 0.0, "target": 0.0, "trigger": "" }
  ],
  "initial_ev": 0.0,
  "stop_loss": 0.0,
  "kelly_criterion": 0.0
}
```

저장: `./reports/{ticker}.md`

---

### STEP 2A — Gemini: 강세 근거 수집 (Bull Intelligence)

다음 프롬프트를 `./claude/gemini_bull_{TICKER}.md`에 저장한다.

```
너는 {TICKER} 종목의 오늘 매수 근거를 수집하는 리서치 어시스턴트다.
Google Search로 최근 7일 이내 긍정적 뉴스와 데이터만 찾아라.

원본 파일: /Volumes/AI/reports/{ticker}.md

## 검색 범위 규칙 (반드시 준수)
- **시간 범위:** 오늘 기준 7일 이내 기사/공시만 인용. 7일 초과 자료는 제외.
- **애널리스트 레이팅:** 14일 이내만 허용.
- **섹션당 최대 3개 출처.** 많은 것보다 정확한 것 우선.
- **직접 검색해서 찾은 URL만 인용.** 기억이나 추론으로 URL을 만들어 쓰는 것 금지.

## 검색 항목 (4개)

1. **오늘의 긍정 뉴스** — "{TICKER} news today", "{TICKER} stock news this week"
   - 주가 상승 촉매가 된 뉴스
   - 계약/파트너십/제품 발표

2. **애널리스트 상향 (14일 이내)** — "{TICKER} analyst upgrade this week", "{TICKER} price target raised"
   - 목표주가 상향 사례 (기관명, 변경 전→후 가격, 날짜)
   - 신규 BUY 전환 사례

3. **실적/가이던스 긍정 신호** — "{TICKER} earnings beat", "{TICKER} guidance raise"
   - 최근 어닝 서프라이즈
   - 가이던스 상향 내용

4. **기관/내부자 매수 공시** — "{TICKER} insider buying Form 4", "{TICKER} institutional buying"
   - SEC Form 4 공시 기반 내부자 매수
   - 기관 신규 편입 공시

## 출력 규칙
- **신뢰도 등급은 [REPORTED] 또는 [UNVERIFIED] 만 사용.**
  [VERIFIED] 태그는 절대 사용 금지 — 검증은 별도 단계에서 Claude가 수행한다.
- 각 근거마다 실제 검색으로 찾은 URL 포함. URL 없으면 [UNVERIFIED]로 표기.
- 수치 없는 주장 금지. 날짜 반드시 포함.
- 분량: 300~500단어 (간결하게)
```

실행:
```bash
GEMINI_CLI_TRUST_WORKSPACE=true ~/.local/bin/gemini --prompt "$(cat /Volumes/AI/claude/gemini_bull_{TICKER}.md)" > /Volumes/AI/reviews/{TICKER}/bull_search.md 2>/dev/null
```

---

### STEP 2B — Gemini: 약세 근거 수집 (Bear Intelligence)

다음 프롬프트를 `./claude/gemini_bear_{TICKER}.md`에 저장한다.

```
너는 {TICKER} 종목의 오늘 매도/리스크 근거를 수집하는 리서치 어시스턴트다.
Google Search로 최근 7일 이내 부정적 뉴스와 리스크 데이터만 찾아라.

원본 파일: /Volumes/AI/reports/{ticker}.md

## 검색 범위 규칙 (반드시 준수)
- **시간 범위:** 오늘 기준 7일 이내 기사/공시만 인용. 7일 초과 자료는 제외.
- **애널리스트 레이팅:** 14일 이내만 허용.
- **섹션당 최대 3개 출처.** 많은 것보다 정확한 것 우선.
- **직접 검색해서 찾은 URL만 인용.** 기억이나 추론으로 URL을 만들어 쓰는 것 금지.

## 검색 항목 (4개)

1. **오늘의 부정 뉴스** — "{TICKER} stock drop reason", "{TICKER} bad news this week"
   - 주가 하락 촉매가 된 뉴스
   - 소송/규제/제재 발표

2. **애널리스트 하향 (14일 이내)** — "{TICKER} analyst downgrade this week", "{TICKER} price target cut"
   - 목표주가 하향 사례 (기관명, 변경 전→후 가격, 날짜)
   - 신규 SELL/UNDERPERFORM 전환 사례

3. **실적/가이던스 부정 신호** — "{TICKER} earnings miss", "{TICKER} guidance cut warning"
   - 어닝 미스 또는 가이던스 하향 우려
   - 이번 주 발표된 리스크 요인

4. **기관/내부자 매도 공시** — "{TICKER} insider selling Form 4 this week", "{TICKER} institutional selling"
   - SEC Form 4 기반 내부자 매도 (10b5-1 프로그램 제외)
   - 기관 대량 매도 공시

## 출력 규칙
- **신뢰도 등급은 [REPORTED] 또는 [UNVERIFIED] 만 사용.**
  [VERIFIED] 태그는 절대 사용 금지 — 검증은 별도 단계에서 Claude가 수행한다.
- 각 근거마다 실제 검색으로 찾은 URL 포함. URL 없으면 [UNVERIFIED]로 표기.
- 수치 없는 주장 금지. 날짜 반드시 포함.
- 분량: 300~500단어 (간결하게)
```

실행:
```bash
GEMINI_CLI_TRUST_WORKSPACE=true ~/.local/bin/gemini --prompt "$(cat /Volumes/AI/claude/gemini_bear_{TICKER}.md)" > /Volumes/AI/reviews/{TICKER}/bear_search.md 2>/dev/null
```

> STEP 2A 완료 후 2B 실행 (Gemini 세션 충돌 방지).

---

### STEP 3 — Claude: 인용 출처 검증 (Fact Verification)

`./reviews/{TICKER}/bull_search.md`와 `./reviews/{TICKER}/bear_search.md`를 읽는다.

**검증 프로세스:**
1. 두 파일에서 URL이 포함된 모든 인용을 추출한다.
2. 각 URL에 대해 `WebFetch`로 실제 접속을 시도한다.
3. 접속 결과에 따라 등급을 부여한다:

| 결과 | 등급 | 가중치 |
|------|------|--------|
| 접속 성공 + 내용 일치 | VERIFIED | 1.0 |
| 접속 성공 + 내용 불일치 | MISLEADING | 0 (플래그) |
| 접속 불가 (paywall 포함) | REPORTED | 0.5 |
| URL 없는 주장 | UNVERIFIED | 0 |

저장 형식 `./reviews/{TICKER}/verified_facts.md`:

```markdown
# Verified Facts: {TICKER}

## 검증 요약
- 전체 인용: N개
- VERIFIED: N개 (XX%)
- REPORTED: N개 (XX%)
- UNVERIFIED/MISLEADING: N개 (XX%)
- 데이터 품질 판정: GOOD / MARGINAL / POOR
  (VERIFIED ≥ 60% → GOOD, 40~59% → MARGINAL, <40% → POOR)

## Bull 근거 (검증됨)
[VERIFIED/REPORTED 항목만, 각 가중치 명시]

## Bear 근거 (검증됨)
[VERIFIED/REPORTED 항목만, 각 가중치 명시]

## 제외된 주장 (UNVERIFIED/MISLEADING)
[이유와 함께 목록화]
```

---

### STEP 4 — GPT: 검증된 사실 기반 독립 점수 산정

다음 프롬프트를 `./claude/gpt_scoring_{TICKER}.md`에 저장한다.

```
너는 퀀트 애널리스트다. 아래 검증된 사실 파일만을 기반으로 점수를 산정하라.
다른 AI의 의견은 무시하고, 순수하게 데이터로만 판단하라.

입력 파일: ./reviews/{TICKER}/verified_facts.md
원본 기술 분석: ./reports/{ticker}.md

## 점수 산정 기준 (각 -10 ~ +10)

### 1. 모멘텀 점수 (기술적)
- RSI: 30 이하 = +3, 70 이상 = -3, 중간 = 0
- MACD: 골든크로스 = +3, 데드크로스 = -3
- 추세: 상승 = +2, 하락 = -2, 횡보 = 0
- 거래량: 평균 대비 150% 이상 돌파 = +2

### 2. 펀더멘털 점수
- PER: 섹터 평균 이하 = +3, 30% 이상 프리미엄 = -3
- EPS 성장률: YoY +20% 이상 = +4, 마이너스 = -4
- PBR: 1 이하 = +2, 3 이상 = -2
- 영업이익률 개선 = +1 / 악화 = -1

### 3. 매크로 점수
- Fed 금리 인하 사이클 = +2, 인상 사이클 = -2
- USD/KRW (한국주식): 원화 강세 = +1, 약세 = -1
- 섹터 성장 사이클 = +2, 수축 = -2

### 4. 리스크 점수
- 내부자 매수 = +3, 내부자 매도 = -3
- 애널리스트 상향 우세 = +2, 하향 우세 = -2
- 소송/규제 이슈 = -3
- 공매도 비율 급증 = -2

### 5. 센티먼트 점수
- 기관 매수 우세 = +2, 매도 우세 = -2
- 어닝 서프라이즈 직후 = +1
- 과도한 낙관론 (소셜 과열) = -1
- 극도의 공포 (역발상 매수) = +2

## 출력 형식

각 차원 점수와 근거를 명시한 뒤 파일 끝에 포함:

```json
{
  "ticker": "{TICKER}",
  "momentum_score": 0,
  "fundamental_score": 0,
  "macro_score": 0,
  "risk_score": 0,
  "sentiment_score": 0,
  "total_score": 0,
  "signal": "STRONG_BUY | BUY | HOLD | SELL | STRONG_SELL",
  "confidence": 0.0,
  "data_coverage": "HIGH | MEDIUM | LOW"
}
```

signal 기준:
- total ≥ +15: STRONG_BUY
- +8 ~ +14: BUY
- -7 ~ +7: HOLD
- -8 ~ -14: SELL
- ≤ -15: STRONG_SELL

UNVERIFIED 데이터는 점수 산정에 사용하지 말 것.
데이터 없는 항목은 0점, "DATA_MISSING" 명시.
분량: 최소 600단어

저장: ./reviews/{TICKER}/gpt_scoring.md
```

실행:
```bash
npx @openai/codex exec --dangerously-bypass-approvals-and-sandbox -s danger-full-access -C /Volumes/AI "$(cat ./claude/gpt_scoring_{TICKER}.md)"
```

---

### STEP 5 — Claude: 통합 최종 리뷰 + 매매 신호 생성

다음 4개 파일을 읽는다:
- `./reports/{ticker}.md`
- `./reviews/{TICKER}/verified_facts.md`
- `./reviews/{TICKER}/gpt_scoring.md`
- `./reviews/{TICKER}/bull_search.md`, `./reviews/{TICKER}/bear_search.md`

**통합 원칙:**
- VERIFIED 가중치 1.0 / REPORTED 가중치 0.5 / UNVERIFIED 완전 제외
- GPT 점수와 기술적 분석이 동일 방향 → 고신뢰도
- 두 분석 충돌 → 신뢰도 LOW → 관망

저장: `./reviews/{TICKER}/final_review.md`

**필수 섹션:**

1. **핵심 판정 요약** (표)
2. **검증된 핵심 팩트** (Bull/Bear 각 상위 3개, VERIFIED/REPORTED만)
3. **제외된 주장 요약** (UNVERIFIED 목록 + 이유)
4. **점수 카드** (GPT 5개 차원 + 총점)
5. **시나리오 재구성** (최소 4개, 확률 합계 100%)
6. **확률 가중 기대값(EV)** (검증된 시나리오만)
7. **매매 판정** (신규 진입 조건, 기존 보유 지침, Kelly 포지션 크기)
8. **실행 플랜** (진입가/목표가1/목표가2/손절가 표)
9. **오늘 당장 체크리스트**
10. **종합 결론** (3문장 이내)

**파일 맨 하단에 매매 신호 JSON:**

```json
{
  "trading_signal": {
    "ticker": "",
    "as_of": "",
    "signal": "BUY | SELL | HOLD | NO_ACTION",
    "signal_strength": "STRONG | MODERATE | WEAK",
    "confidence": 0.0,
    "data_quality": "GOOD | MARGINAL | POOR",
    "entry": {
      "price_min": 0.0,
      "price_max": 0.0,
      "condition": ""
    },
    "position_sizing": {
      "kelly_fraction": 0.0,
      "recommended_pct": 0.0,
      "max_loss_pct": 0.0
    },
    "targets": [
      { "level": 1, "price": 0.0, "sell_pct": 0.0 },
      { "level": 2, "price": 0.0, "sell_pct": 0.0 },
      { "level": 3, "price": 0.0, "sell_pct": 0.0 }
    ],
    "stop_loss": 0.0,
    "signal_expiry": "",
    "invalidation_conditions": [],
    "verified_bull_count": 0,
    "verified_bear_count": 0,
    "unverified_excluded_count": 0
  }
}
```

**신호 생성 규칙:**
- `data_quality: POOR` → signal 강제로 `NO_ACTION`
- GPT 점수와 기술적 추세 반대 방향 → confidence 최대 0.5 cap
- VERIFIED 근거 3개 미만 → signal 강제로 `HOLD` 또는 `NO_ACTION`
- kelly_fraction 절대 0.25 초과 금지

신호 JSON을 `./logs/signals/{TICKER}_{YYYYMMDD}.json`에도 별도 저장한다. (자동매매 시스템 입력용)

---

### STEP 6 — 예측 로그 기록

`./logs/prediction_log.md`에 추가 (기존 내용 보존):

```markdown
---
## {TICKER} | {날짜} | {신호}
- 분석 시 현재가: {price}
- 최종 신호: {signal} ({signal_strength}) | 신뢰도: {confidence} | 데이터 품질: {data_quality}
- 진입 조건: {entry.condition}
- 목표가: {target_1} / {target_2} / {target_3} | 손절가: {stop_loss}
- 신호 만료: {signal_expiry}
- 검증 근거: Bull {verified_bull_count}개 / Bear {verified_bear_count}개 / 제외 {unverified_excluded_count}개
- 실제 결과: [미기록]
- 예측 정확도: [미기록]
```

---

### STEP 7 — 완료 보고

- 생성 파일 목록
- 최종 신호 + 신뢰도 + 데이터 품질
- 검증된 근거 수 (Bull/Bear)
- 진입 조건 한 줄 요약 + 손절가
