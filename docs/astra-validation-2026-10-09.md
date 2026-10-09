# Astra 방어 분류 준비 및 검증

- 요청 모델: `gpt-6-astra`, OpenAI 공식 API. 인증된 모델 조회 HTTP 200 확인. 모델 생성 호출은 미실행.
- 일반 정책과 입력 8건은 기존 Qwen·Opus 실험과 동일하게 사용할 예정이었다. 외부 원문 전송은 자동 승인 검토에서 차단됐고, 추가 질문에는 사용자가 Isaac 정상 동작 증명을 우선 요구했다. 따라서 코퍼스 전송은 보류했다.
- `openai` provider를 추가했다. 고정 공식 API URL, `OPENAI_API_KEY` 또는 `OPENAI_KEY`, `max_completion_tokens=1024`, `reasoning_effort=low`, `store=false`. 거부·불완전 출력·오류는 HOLD. 새로운 공격 생성이나 실행은 하지 않는다.
- `.env.example`에 사용자가 넣은 실제 키는 `.env`로 옮기고 템플릿은 비웠다. `.env`는 Git 제외 확인. 템플릿을 읽는 중 키가 도구 출력에 노출돼 사용자에게 재발급을 권고했다. 이 문서에는 키 값을 기록하지 않는다.
- 전체 pytest: 56 passed, upstream Starlette TestClient deprecation 1건. 추가 테스트에서 변경 전 파라미터·provider 오류 2건 실패를 확인한 뒤 구현했다.
- 독립 리뷰: `/root/review_astra_guard`, 실제 생성 설정 `gpt-6-luna` / `max`, 읽기 전용. guard/corpus/Engine 호출 경로, 테스트, 템플릿과 문서 확인. P0~P2 없음.
- P3 1건: 기존 BLOCK/NORMAL 조합이 범주상 모순이어도 BLOCK으로 기록됨. 실행은 여전히 차단되므로 이번 provider 추가에서는 유지했다. 범주별 분석에서는 이런 조합을 정상 탐지 근거로 해석하면 안 된다.
- 실제 Astra 탐지율·지연 측정, SA별 방어 성능, Isaac 정상 작업 성공은 아직 입증하지 않았다.

공식 문서: https://developers.openai.com/api/docs/models/gpt-6-astra 및 https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
