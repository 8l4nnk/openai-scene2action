# 기존 Isaac 환경 이관 기록

## 현재 선택한 Pod (사용자 변경 지시)

### 공개 뷰어 배포 후속 기록

- 공개 주소: https://80wnh6z0nu0o82-8888.proxy.runpod.net/ . 읽기 전용 카메라·결과 뷰어이며 실행 API는 없다.
- 8888/http 추가 시 Runpod가 컨테이너를 재생성했다. `/workspace`는 유지됐지만 `/opt/ros`는 사라져, 기존 `experiment-env/restore-environment.sh`로 복원했고 종료 코드 0 및 CUDA 가용 상태를 확인했다.
- 정상 실행은 별도 ROS 도메인 110, `/workspace/s2a_normal_validation_20261009/live`를 사용한다. 이전 READY 파일을 현재 실행 성공으로 사용하지 않는다.
- 배포 빌드 `build-c18d9a6b3241`은 6개 파일을 같은 폴더에 배치한다. 번들 SHA-256 `c18d9a6b3241c0ed02c8727562028a5a4cdc7cb74bc486abcadc663c0961bc16`.
- 시작 대기 상태를 보완한 뷰어는 `viewer-startup.py`, SHA-256 `5fd2eeb2f5434cb5c24f57c28abb9e71a1581e0bb28e612a1e5f90885677eccb`.
- 독립 리뷰 `/root/review_l4_normal_deploy`, 생성 요청 `gpt-6-luna` / `max`. 관측 세대 일치, 안착 판정, 취소 후 정지 확인 지적을 수정했고 마지막 재검토 지적 없음. 관련 테스트 4개 및 추가 뷰어 시작 테스트 통과.
- 아래의 '재시작하지 않았다'는 최초 접속 당시 기록이다. 공개 포트 배포 과정의 재시작과 복원은 위 후속 기록이 우선한다.

- 2026-10-09 사용자 지시로 작업 기준을 `scene2action-l4-throw-replay-20261007-migration` (`80wnh6z0nu0o82`)으로 변경했다.
- 해당 Pod는 NVIDIA L4, 기존 PyTorch 이미지, `/workspace`의 네트워크 볼륨 `z07xtou7jt`를 사용 중이다. 조회 시 RUNNING, GPU 사용률 100%, API GPU 요금은 시간당 $0.59였다.
- 사용자 승인 후 해당 Pod의 웹 터미널을 활성화하고 접속했다. 기존 Isaac 진입점은 `/workspace/codex_jaewoo_20261009/experiment-env/runtime/isaac_ros2_control_entry_local.py`이다. 실행 설정·장면·기존 프로세스를 변경하거나 재시작하지 않았다.
- `/workspace/codex_jaewoo_20261009/results/environment-readiness.json` 및 `live/status.json`에서 `READY`를 확인했다. 실행 장면은 `/workspace/k2a/ros2_moveit/attack_scene_g90/results/S05/ros2-attack-scene-knife90-clear-v9.usda`이다. 이는 환경 상태 파일의 보고이며, 정상 운반 성공이나 웹 시뮬레이션 연결 완료를 의미하지 않는다.
- 이번 변경은 작업 대상과 접속 전환이다. 아래 이전 4090용 실행 스크립트를 L4에 배포하지 않았다. 기존 서비스와 충돌하지 않도록 L4의 실행 중인 환경을 기준으로 후속 연결을 진행한다.
- 아래 4090 이관 기록은 이전 대상의 결과다. `t98v7b6lrm0frg`는 중복 GPU 비용을 줄이기 위해 중지했다. 원본 및 이관 파일이 있는 볼륨은 보존했다.
- 이전 대상은 05:47:33 UTC 로그에서 ENVIRONMENT_READY, 필수 개체 6개 존재, 미해결 에셋 0개, 원본 해시 일치를 보고했다. 정상 운반 및 필터 통합 검증은 false이며, 이 결과를 새 L4 Pod 검증으로 사용하지 않는다.

## 범위

새로 조립한 normal_baseline 장면 대신, 기존 Pod의 저장된 `environment.usdc`, 에셋, 실행 소스를 가져온다. 원본 장면을 USD로 읽어 참조를 합성하고 파일 의존성 경로를 이관 폴더로 바꾼 실행용 사본을 만든다. 형상·배치·물리 파라미터를 새로 정의하지 않는다.

- 원본: `/workspace/environments/isaac_tools_worker_clone_yq1s3wwmt41ng1_20260929`
- 원본 환경 이름: `S05-imported-tools-construction-worker-v6` (작업대 높이 1m, 확대된 작업대·공·도구 포함)
- 이관본: `/workspace/scene2action_migrated_20261009/original`
- 실행 코드: `/workspace/scene2action_migrated_20261009/runtime`
- 이관 명세: `/workspace/scene2action_migrated_20261009/manifest.json`
- 대상 Pod: `t98v7b6lrm0frg`, 공식 Isaac Sim 6.1 이미지
- 조회: https://t98v7b6lrm0frg-8888.proxy.runpod.net/

기존 볼륨 `vkl35ayv3y`의 용량 부족으로 쓰기가 실패했다. 사용자의 명시적 승인 후 150GB에서 160GB로 증설했다. 표준 저장소 비용은 월 약 $0.70 추가된다. Pod의 GPU 비용은 시간당 $0.89이다. 두 번째 네트워크 볼륨은 API에서 동시 연결이 거부되어, 새로 만든 미사용 10GB 볼륨을 삭제하고 404로 삭제를 확인했다.

## 확인한 증거

- 80개 원본 파일의 복사 전후 SHA-256 일치.
- 원본 USD SHA-256: `c4650a0e482068de885d673d275d3b5c5c2a9c2eef47a337701d940ef1b5a757`
- 원본 경로는 변경하지 않았으며, 복사된 기존 실행기나 모델 에이전트는 자동 실행하지 않는다.
- 프로젝트 에셋은 `runtime/assets`로 모으고 해시를 기록한다. Isaac에 기본 제공되는 MDL 재질은 런타임 의존성으로 별도 기록한다.
- 저장된 장면의 과거 그래프와 렌더 출력은 실행 사본의 메모리 레이어에서만 제거하고 새 렌더 그래프를 생성한다. 필수 6개 작업 개체는 다시 확인하며, 원본 파일은 저장·덮어쓰기하지 않는다.
- 실제 장면 열기·필수 개체·렌더 결과는 `render-verification.json`과 공개 페이지 상태로 확인한다. 파일 복사만으로 렌더 성공을 선언하지 않는다.

## 검증 및 리뷰

- 이관 회귀 테스트: 2 passed. 버전 검사 포함 관련 테스트: 8 passed.
- Python 문법 검사 통과. 배포 시 Linux `bash -n` 검사 수행.
- HTTP 확인: 페이지 및 상태 조회 200, 비공개 소스 경로 404, 존재하지 않는 이미지 503, POST 501. 상태 응답은 허용한 필드만 반환한다.
- 독립 리뷰어: `/root/review_isaac_migration`, 생성 설정 `gpt-6-luna` / `max`.
- 파일 형식 누락, 경로 중첩, MDL 의존성 경로 지적을 수정하고 재검토에서 지적 사항 없음 판정을 받았다.
- 최종 런타임 4개 파일 번들 SHA-256: `614c23f136911c678a18f1c57f43ee60bbefe58d179412658caeb7f8de1295b7`.

## 구분해야 할 결과

이번 이관 검사는 기존 장면과 에셋이 새 런타임에서 열리고 렌더되는지 확인한다. Direct IK의 정상 운반 성공, F2 → Adapter → Isaac 통합, SA02–SA17 방어 성능은 별도 검증 대상이다. 공개 웹에는 명령 실행·셸·키·과거 공격 데이터 조회 기능이 없다. 기존 소스의 구형 런타임 경로가 들어 있는 `original/run.sh`를 바로 실행하는 대신, 새 런타임 래퍼 `runtime/run_isaac_migrated.sh`를 사용한다.
