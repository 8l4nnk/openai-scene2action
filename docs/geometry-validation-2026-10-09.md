# Python/C++ 충돌 검사 패치 검증

2026-10-09. Python 앱·모델 호출·기록 계층은 유지하고, F3의 정규화 2D 충돌 검사에 선택 가능한 C++17 커널을 추가했다. 평가, 실행 직전 재검증, 이동 tick에서 같은 엔진별 백엔드를 사용한다. C++ 라이브러리가 필요하도록 설정한 상태에서 파일·ABI가 잘못되면 시작에 실패하며 Python으로 자동 대체하지 않는다.

## 실행 방법

설치된 clang++ 또는 g++ 호환 컴파일러로 한 번 빌드한다. 애플리케이션 시작 시 컴파일러를 실행하지 않으며, 바이너리는 Git에서 제외된 `.data/native`에 생성한다.

```powershell
uv run python scripts/build_native.py
$env:S2A_GEOMETRY_BACKEND='native'
uv run --env-file .env python -m scene2action
```

`S2A_NATIVE_LIBRARY`로 서버 운영자가 라이브러리 경로를 지정할 수 있다. 외부 입력과 모델 응답에는 백엔드 또는 라이브러리를 선택할 권한이 없다. 기본 백엔드는 `python`이다. 실제 선택은 `/api/state`와 실행 기록의 `evidence.geometry_backend`에 남는다.

## 검증

- 실제 Windows DLL을 사용한 경계·접촉·운반 반경·잘못된 좌표·NaN/무한대 검사와 결정적 랜덤 입력 500건의 Python/C++ 판정 일치 확인.
- C++ 경로로 색상 분류와 키트 준비의 정상 완료, 정지 후 위치 유지 및 승인 재사용 차단 확인.
- 모델 대기 중 기존 승인 작업의 감시 이동과 STOP 응답, 대기 중 후보의 HOLD 및 명령 미전달 확인. 외부 모델은 호출하지 않았다.
- 전체 테스트: Python 기본 경로와 native 경로 각각 94 passed, 1 skipped, 1 upstream Starlette deprecation warning. 건너뛴 검증은 Windows에서 심볼릭 링크 생성 권한이 필요한 별도 Isaac 증거 테스트였다.
- C++는 상태·I/O·동적 할당 없는 제한된 연산 함수이며 `ctypes.CDLL` 호출 중 GIL을 해제한다. Python 검증과 데이터 포장은 Python에서 수행한다.

## 측정

각 조건 200회. 양쪽에 같은 입력을 제공하며 Python 검증과 ctypes 포장 비용을 포함했다. 단위 µs, p50은 중앙값 순위다.

| 이동 구간 | 장애물 | Python p50 | C++ p50 | p50 비율 | Python p95 | C++ p95 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 8 | 0 | 26.0 | 13.9 | 1.87배 | 35.6 | 14.9 |
| 16 | 128 | 3306.3 | 445.3 | 7.43배 | 4402.4 | 850.1 |
| 64 | 512 | 36042.2 | 999.7 | 36.05배 | 56040.9 | 1476.7 |

장애물은 합성 반복 AABB이며 경로가 모두 비충돌인 연산 비교용 조건이다. HTTP·모델·데이터베이스·Isaac·로봇 정지 시간은 제외했다. 시스템 부하에 영향을 받는 관측값이며 실시간 처리 상한 또는 제품 전체 속도 향상을 보장하지 않는다.

```powershell
$env:S2A_GEOMETRY_BACKEND='native'
uv run python -m scene2action.geometry_benchmark --samples 200
```

## 남은 범위

실행 감시는 기존 Python 스레드다. 별도 C++ 제어 프로세스, 3D 로봇 충돌·관절·그립 힘 검사와 실제 제어기 정지 검증은 이번 패치에 포함되지 않는다. Isaac 정상 작업 완료와 SA 전체의 물리 안전은 별도 검증해야 한다. 모델 응답 지연도 이 패치로 줄어들지 않는다.

## 최종 확인

독립 리뷰어 `/root/review_native_geometry_final`, 실제 생성 요청 모델 `gpt-6-luna`, 추론 `max`. 지정된 코드·테스트·앱 호출 경로를 직접 읽고 시작/종료 시 SHA-256 9개가 같음을 확인했다. P0~P3 지적 없음. 리뷰어는 파일 수정이나 테스트 실행을 하지 않았다.

DLL 재빌드 후 native 사용을 필수로 지정한 geometry/API 검증은 30 passed, upstream warning 1건. JavaScript 구문 검사 통과. 코드 해시는 리뷰 종료 후에도 변경되지 않았다.

로컬 워크벤치를 `S2A_GEOMETRY_BACKEND=native`로 재시작했다. HTTP 200 상태에서 `geometry_backend=native`, 활성 실행 없음, fault 없음과 기존 Qwen3-VL-32B 입력 필터 설정을 확인했다. 상태 조회만 했으며 새 모델 호출이나 로봇 실행은 하지 않았다. 설정은 해당 서버 프로세스 환경에 적용했다. 다음 실행에는 위 명령으로 native를 선택해야 한다.
