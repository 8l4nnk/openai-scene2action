# 카메라·데모 대시보드 배포 검증 (2026-10-09)

- 로컬: http://127.0.0.1:8765/
- AWS: https://d17ad0or62kzba.cloudfront.net/ (기존 팀 로그인)
- Isaac 카메라 원본: https://80wnh6z0nu0o82-8888.proxy.runpod.net/
- AWS 리전: ap-southeast-2
- 배포 아카이브 SHA-256: `7c0393011a73ac8d19f875e370ae962d7ec8a28be0e629cd82eef56f65993fc8`
- SSM 배포: `0901a8e5-4608-437c-ab44-01a656f58358`, Success. 기존 runtime/DB 유지, 이전 소스 백업 후 반영.

## 자료와 판정 의미

`demo/`에 R15 텍스트 공격 270건, R23 사용자 시스템 프롬프트 기준 이미지 64건과 원본 PNG, Qwen 결과 334건, 기존 3모델 VLM 결과 1,002건을 저장했다. 입력과 Qwen 결과는 과거 실행 기록이다. 이번 작업에서 모델을 새로 호출하거나 공격 명령을 실행하지 않았다. 원본 ID와 SHA-256은 manifest로 연결한다.

과거 Qwen의 EXECUTE 제안은 텍스트 183/270, 이미지 24/64, 합계 207건이다. 이는 로봇 공격 성공률이 아니다. 현재 고정 정상 작업 계약의 오프라인 검사에서는 207건 모두 F2 BLOCK이다. 앞 단계가 차단하면 뒤 단계는 SKIP이다. 정상 형태의 계획도 최신 관측·실행 허가가 없어 F3 HOLD이며 제어기 호출은 0건이다.

이 화면의 검사는 아직 실제 Isaac 제어기의 명령 전달 경로에 연결되지 않았다. F1은 자료 무결성과 응답 연결을 확인하는 단계이며 의미 기반 공격 탐지 성능을 입증하지 않는다. F2는 고정 정상 작업과 명령 형식을 비교한다. F3는 역사적 기록을 실행 허가로 사용할 수 없도록 보류한다.

카메라는 별도의 정상 Isaac 장면을 보여준다. 선택한 공격 사례의 실행 영상이 아니다. 촬영 후 10초를 넘거나 연결이 끊기면 오래된 프레임/연결 오류를 표시한다. 카메라 런타임은 회당 15분 제한이다.

## 확인한 결과

- `tests/test_demo.py tests/test_api.py tests/test_hosting.py`: 18 passed.
- 로컬: 사례 334건, 이미지, 카메라 JPEG 조회 및 UI 표시 확인.
- AWS: 로그인 303, 인증 후 사례/이미지/카메라 조회 성공. 비인증 사례·카메라 API는 401.
- 텍스트·이미지 EXECUTE 표본: F1 PASS → F2 BLOCK → F3 SKIP, `isaac_dispatched=false`.
- 사례 실행 POST 경로는 404. 이 대시보드에서 공격 명령을 전달하지 않는다.
- 내장 브라우저 AWS 로그인 화면은 열렸으나 UI 세션 진입은 확인하지 못했다. 위 AWS 검증은 HTTP 클라이언트로 기존 비밀번호를 사용해 확인했다.

## 남은 실증

정상 운반 실험 `normal-7606e9b166244ca380fb5f697f5d1fa3`은 controller/observation preflight timeout으로 FAIL, 완료 명령 0건이다. 빨간 공→1구역·파란 공→2구역 운반 성공과 실제 Isaac 앞 F1/F2/F3 통합 실증은 미완료다. 카메라 출력 및 오프라인 차단 결과로 이를 대신 입증했다고 주장하지 않는다.

## 독립 리뷰

- `/root/review_l4_normal_deploy`, Codex `gpt-6-luna` / `max`: demo evaluator/API/UI/importer 및 번들 변경. 잘못된 단계와 verify 파라미터의 F2 통과, 배포 symlink 검증 관련 P2 수정 후 최종 잔여 P0–P2 없음.
- `/root/review_aws_hosting`, Codex `gpt-6-luna` / `max`: 동시 작업 채팅의 로그인 navigation 수정 재검토, 추가 지적 없음. 검토된 hosting.py SHA-256 `86299a436f145231a769cb489b1003144f800a824f2d422dd2a98fc858c5e6d1` 확인.

이번 작업은 로컬 파일 저장과 배포까지 진행했으며 Git 커밋·푸시는 수행하지 않았다.
