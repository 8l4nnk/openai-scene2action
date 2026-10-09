# AWS 로그인 오류 수정 — 2026-10-09

비밀번호 입력 후 로그인 폼을 제출하면 `Same-origin request required`가 표시되던 오류를 수정하고 기존 AWS 서버에 반영했다. 비밀번호와 세션 서명키는 변경하지 않았다.

## 원인과 변경

로그인 페이지 응답에 `Referrer-Policy: no-referrer`를 지정하면서 POST 요청에는 공개 HTTPS 출처와 정확히 같은 Origin을 요구했다. 브라우저의 폼 제출은 navigation 요청이므로 이 정책에서 `Origin: null`이 되어 정상 로그인도 403으로 거부됐다. [Fetch Standard의 Origin 헤더 규칙](https://fetch.spec.whatwg.org/#append-a-request-origin-header)과 실제 로컬 Chrome 폼 제출로 확인했다.

`scene2action/hosting.py`의 로그인 게이트웨이 응답 정책을 `same-origin`으로 변경했다. 같은 출처의 로그인 요청은 출처를 유지하고 외부 사이트로의 referrer 전송은 억제한다. 누락된 Origin, null Origin, 외부 Origin 거부, 인증, 쿠키, 로그인 시도 제한은 유지한다. CloudFront 응답 헤더 정책의 ReferrerPolicy Override는 false이므로 서버 응답을 덮어쓰지 않는다.

로그인 폼 정책과 정상 요청·누락/null/외부 Origin 거부를 확인하는 회귀 검증을 `tests/test_hosting.py`에 추가했다. 다른 채팅이 추가한 영상 인증 검증 2줄도 현재 파일에 포함해 리뷰했다.

## 검증

- 회귀 테스트 RED: 기존 응답 정책 `no-referrer`에서 실패 확인.
- 호스팅·API 테스트: 14개 통과.
- 전체 최종 pytest: 122개 통과, 1개 건너뜀, 기존 Starlette 경고 1개. 첫 실행에서 다른 채팅의 진행 중 demo 구현 때문에 실패했던 2건도 구현 완료 후 통과했다.
- 별도 프로필의 로컬 headless Chrome이 실제 로그인 HTML 폼을 제출: 기존 정책에서는 Origin null / 403, 수정 정책에서는 정상 Origin / 303.
- Python compileall과 배포 스크립트 bash -n 성공.
- SSM 운영 검증: GET /login 200, Referrer-Policy same-origin, null Origin POST 403, 앱과 Nginx 각각 active, 배포 SHA 일치.

공개 AWS 도메인의 브라우저 접근은 이전 권한 거절을 우회하지 않았다. Chrome 검증은 localhost 전용이며 운영 검증은 승인된 EC2의 SSM과 Nginx 경로를 사용했다. 실제 로봇·Isaac 구동은 수행하지 않았다.

## 독립 리뷰와 배포

리뷰어 `/root/review_aws_hosting`, 최초 생성 요청 설정 `gpt-6-luna` / `max`. 범위는 hosting.py, test_hosting.py, 단일 파일 배포 스크립트 및 관련 인증/프록시 호출 경로다. 배포 스크립트의 최종 서비스 확인과 롤백 순서에 관한 P3 1건을 수정했고 재검토에서 해결 및 추가 지적 없음 판정을 받았다. 리뷰어는 파일 수정이나 배포를 수행하지 않았다.

운영 서버에 hosting.py 한 파일을 비공개 암호화 S3 releases 객체를 통해 교체했다. 기존 SHA 검사, 백업, 실패 시 복구를 포함했고 서비스 재시작 뒤 검증했다. 다른 채팅이 작업 중인 영상·demo·정책 파일은 이 배포에서 변경하지 않았다.

- 공개 로그인: https://d17ad0or62kzba.cloudfront.net/login
- EC2: i-0e5a5af8faa0274c3 / ap-southeast-2
- 이전 hosting SHA256: 86299a436f145231a769cb489b1003144f800a824f2d422dd2a98fc858c5e6d1
- 최종 hosting SHA256: 9ceb9ff5b2d99ad21b4cb4e133917910fe7a9110e40e1bb25e9149aa486f9ab4
- SSM 배포 명령: 2aaf4608-d571-42bf-868d-827d9dc7ee34 / Success / exit 0
- 백업: /opt/scene2action/backups/hosting-before-referrer-9ceb9ff5b2d99ad21b4cb4e133917910fe7a9110e40e1bb25e9149aa486f9ab4.py

서버와 기존 AWS 리소스는 사용자의 유지 요청에 따라 계속 실행한다. 비밀번호는 로컬 .data/aws-deploy/access.txt에 있으며 이 문서에는 포함하지 않는다.
