# stock-batch-v2

**목적:** 여러 종목을 v2 파이프라인으로 순차 분석 + DB 자동 저장 + 비교 요약
**사용법:** `/stock-batch-v2 TICKER1 TICKER2 TICKER3 ...`
**예시:** `/stock-batch-v2 AMD MSFT META GOOGL AMZN`
**원칙:** 순차 실행. Gemini quota 보호를 위해 종목 간 10초 대기.

---

## 실행 구조

```
TICKER1 → v2 6단계 → DB insert → TICKER2 → v2 6단계 → DB insert → ... → 비교 요약
```

각 종목이 완전히 끝난 후 다음 종목으로 넘어간다.
Gemini 실패 시 Claude WebSearch fallback으로 계속 진행 (중단 없음).

---

## 파이프라인

`$ARGUMENTS`에서 티커 목록을 추출한다 (공백 또는 쉼표 구분).
이하 `{TICKER}` = 대문자, `{ticker}` = 소문자.

---

### 사전 준비

```bash
python3 /Volumes/AI/scripts/init_db.py 2>/dev/null || true
```

DB가 없으면 생성, 있으면 그대로 진행.

---

### 각 종목 반복 (STEP 1~6)

아래 STEP 1~6을 각 티커마다 순서대로 실행한다.

---

#### STEP 1 — TradingView MCP Feature Extraction

`/Volumes/AI/.claude/commands/stock-review_v2.md`의 STEP 1 지침을 따른다.

저장:
- `./reviews/{TICKER}/market_features_v2.json`
- `./reports/{ticker}_v2.md`

---

#### STEP 2 — Gemini Evidence Collection

프롬프트를 `./claude/gemini_evidence_{TICKER}_v2.md`에 저장 후 실행:

```bash
mkdir -p /Volumes/AI/reviews/{TICKER}
GEMINI_CLI_TRUST_WORKSPACE=true ~/.local/bin/gemini -m gemini-2.5-pro \
  --prompt "$(cat /Volumes/AI/claude/gemini_evidence_{TICKER}_v2.md)" \
  > /Volumes/AI/reviews/{TICKER}/evidence_raw_v2.json 2>/dev/null
```

**Gemini 실패 시 (exit 1 또는 빈 파일):** Claude WebSearch로 직접 수집.
실패해도 다음 단계로 계속 진행한다.

---

#### STEP 3 — Evidence Validation

`/Volumes/AI/.claude/commands/stock-review_v2.md`의 STEP 3 지침을 따른다.

저장: `./reviews/{TICKER}/evidence_validated_v2.json`

---

#### STEP 4 — Probabilistic Scenario Generation

프롬프트를 `./claude/gpt_scenario_{TICKER}_v2.md`에 저장 후 실행:

```bash
npx @openai/codex exec --dangerously-bypass-approvals-and-sandbox \
  -s danger-full-access -C /Volumes/AI \
  "$(cat /Volumes/AI/claude/gpt_scenario_{TICKER}_v2.md)" \
  > /Volumes/AI/reviews/{TICKER}/scenario_forecast_v2.json 2>/dev/null
```

GPT 실패 시 Claude가 직접 시나리오 생성.

저장: `./reviews/{TICKER}/scenario_forecast_v2.json`

---

#### STEP 5 — Final Review

`/Volumes/AI/.claude/commands/stock-review_v2.md`의 STEP 5 지침을 따른다.

저장: `./reviews/{TICKER}/final_review_v2.md`

---

#### STEP 6 — DB Insert

분석 완료 후 즉시 DB에 저장:

```bash
python3 /Volumes/AI/scripts/db_insert.py {TICKER}
```

저장 확인:
```bash
python3 /Volumes/AI/scripts/db_utils.py list
```

종목 간 대기:
```bash
# 다음 종목 전 Gemini quota 보호
# (Claude가 10초 대기 후 다음 종목 시작)
```

---

### 전체 종목 완료 후 — 비교 요약

모든 종목 분석이 끝나면 아래 비교 테이블을 출력한다.

```markdown
## 배치 분석 완료 요약 — {날짜}

| 티커 | 기준가 | primary scenario | p50 | conf | 품질 | 핵심 근거 1개 |
|------|--------|-----------------|-----|------|------|--------------|
| NVDA | $198.45 | neutral | +1.4% | 0.58 | GOOD | Q1 가이던스 $78B |
| ...  | ...    | ...             | ... | ...  | ...  | ...          |

### 상위 conviction 종목 (confidence 높은 순)
[자동 정렬]

### 주의 종목 (data_quality POOR 또는 confidence < 0.5)
[자동 필터]

### DB 저장 현황
전체 예측: N개 | 이번 배치: N개 신규
```

---

## 오류 처리 원칙

| 상황 | 대응 |
|------|------|
| Gemini quota 소진 | WebSearch fallback, 계속 진행 |
| TradingView 연결 실패 | tv_launch 재시도 1회, 실패 시 WebSearch로 가격 수집 |
| GPT 실패 | Claude 직접 시나리오 생성 |
| 특정 종목 전체 실패 | 해당 종목 스킵 후 다음 종목 진행, 최종 요약에 실패 표시 |

---

## 완료 보고

- 분석 완료 종목 수 / 전체
- 실패 종목 (있을 경우)
- DB 저장 건수
- 가장 높은 confidence 종목
- 가장 낮은 data_quality 종목
