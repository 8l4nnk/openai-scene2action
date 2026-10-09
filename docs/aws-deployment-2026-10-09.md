# AWS 대시보드 초기 배포 기록

주소: https://d17ad0or62kzba.cloudfront.net/

프로젝트 AWS ID 209308108679, 선택 리전 ap-southeast-2. 기존 scene2action 로그인 프로필 사용. AWS Settings > View all projects > Overview > Additional Info > Region에서 프로젝트 리전도 확인할 수 있다.

## 구성

- EC2 i-0e5a5af8faa0274c3, t3.small/standard CPU credits, 암호화 gp3 20GB. SQLite 및 한 프로세스의 실행 상태를 유지한다.
- CloudFront E6SZ1R4T5F6I8, 기본 HTTPS 도메인, VPC origin vo_7EEStaFYMjzFmnf9KpphwB. 캐시 비활성화, 쿠키·Origin 전달, 관리 보안 응답 헤더.
- EC2 보안 그룹 sg-04dbab4dee50dbd5f는 CloudFront 서비스 그룹 sg-0dc9c46c6500250f4의 TCP80만 허용한다. 공개 IP 직접 접속·SSH 차단을 확인했다. 공개 IPv4는 SSM 및 패키지 설치 등 송신에 사용한다.
- Nginx → loopback Uvicorn, worker 하나. Linux C++17 네이티브 검사 라이브러리로 실행. 실제 로봇이나 Isaac GPU 실행이 없는 2D 워크벤치다.
- 팀 비밀번호 로그인, 서명된 8시간 세션, Secure/HttpOnly/SameSite=Strict 쿠키. 로그인은 신뢰된 IP별 5회/분 제한, Host·Origin 검사. 기존 로컬 실행 경계 유지.
- 비공개·암호화 S3 scene2action-209308108679-demo-20261009. 소스와 runtime만 저장. 사용자 승인 후 OpenRouter 키 한 개만 runtime에 복사했다. OpenAI 키·로컬 기록·공격 데이터는 전송하지 않았다.
- WAF는 CloudFront 범위로 us-east-1에 생성했고 배포에 연결했다. 초기 Count 관측 모드이며 차단 임계값 튜닝이 남아 있다. Cookie/Authorization을 가린 로그, 7일 보관, 요청 샘플링 비활성화. CloudFront용 글로벌 WAF 및 그 로그만 us-east-1을 사용한다.

## 검증 및 독립 리뷰

초기 호스팅/API 테스트 12개 통과(기존 upstream 경고 1건), Python compileall 및 JavaScript node --check 통과. 실제 배포한 초기 번들은 30개 소스 파일이며 SHA256은 89fde2a0c6c8baad068a7b3d1b639298a59c57b0bc6b64edb6c8db1416701fff.

리뷰어 /root/review_aws_hosting, 실제 생성 설정 gpt-6-luna / max / fork_turns=none. 읽기 전용으로 호스팅 게이트, 배포 스크립트·설정·번들 및 기존 앱/엔진 호출 경로를 검토했다. P1 AL2023 awscli 패키지명, P2 전역 로그인 차단, P2 동시 로그인 제한 경합을 수정했고 재검토에서 세 항목 해결·추가 유효 지적 없음으로 확인했다.

추가 공유 링크 진입 수정: Origin이 없는 GET / 또는 GET /login에서 Fetch Metadata가 문서 탐색인 경우에만 공개 로그인 진입을 허용한다. 개인 API, 탐색이 아닌 cross-site 요청, POST는 거부를 유지한다. 이 수정의 로컬 호스팅/API 테스트는 13개 통과했고 같은 리뷰어의 재검토에서도 추가 지적 없음이다. hosting.py SHA256은 86299a436f145231a769cb489b1003144f800a824f2d422dd2a98fc858c5e6d1.

이 추가 수정은 원본 ‘이전 작업 가져오기’ 채팅이 진행하는 카메라·334건 demo 데이터의 통합 배포에 포함하도록 준비됐다. 사용자의 다른 채팅에서 local+AWS 갱신과 배포 조율을 승인한 사실을 확인했다. 충돌을 피하기 위해 이 초기 배포 채팅은 추가 원격 배포를 수행하지 않는다. 다른 채팅이 수정한 demo/·app/static·bundle 파일을 보존했다. 현재 로컬 release.tar.gz는 통합 작업의 산출물이므로 위 초기 배포 해시와 구분해야 한다.

실제 공개 HTTPS API 검증:

- 비로그인 API 401, 로그인 303, 로그인 후 대시보드 200.
- 실제 backend=native 및 Qwen qwen/qwen3-vl-32b-instruct guard 활성 확인.
- 정상 작업 문장 한 건의 평가 READY, 시뮬레이션 RUNNING 및 실제 위치 변화 확인.
- 정지 STOPPED, 정지한 승인 재사용 409, 외부 Origin 요청 403.
- 인증 정보가 없는 공개 IP 직접 접속은 차단됨.

원시 검증 결과는 .data/aws-deploy/verification.json, 리소스 목록은 .data/aws-deploy/deployment.json, 접속 비밀번호는 .data/aws-deploy/access.txt에 저장한다. 모두 Git 제외 경로다. 브라우저 접근 승인이 거절되어 공개 UI 화면 캡처는 수행하지 못했다. API 검증은 그 이전에 완료했다.

## 운영

서버는 요청한 호스팅을 위해 실행 상태로 유지한다. 프로젝트는 FREE/ACTIVE이며 배포 전 USD100 크레딧을 확인했다. EC2·디스크·공개 IPv4·WAF 등 사용량은 크레딧을 소비하므로 AWS Settings > Billing에서 잔액을 확인한다.

중지·정리는 사용자 요청 후 수행한다. EC2 중지 후 재시작하면 이전 실행 승인은 무효화된다. 루트 EBS는 DeleteOnTermination=false이므로 인스턴스를 종료해도 기록 디스크가 남고 저장 비용이 계속 발생한다. 정리 시 필요한 기록을 먼저 보관한 뒤 CloudFront/VPC origin, EC2, EBS, WAF/log group, S3 runtime/artifacts, 전용 IAM role/profile을 함께 점검한다. 이번 배포에서 유료 플랜 전환이나 팀원 권한 변경은 수행하지 않았다.

CloudFront 관리: https://us-east-1.console.aws.amazon.com/cloudfront/v4/home?region=us-east-1#/distributions/E6SZ1R4T5F6I8

WAF 관리: https://us-east-1.console.aws.amazon.com/wafv2/homev2/web-acls?region=us-east-1
