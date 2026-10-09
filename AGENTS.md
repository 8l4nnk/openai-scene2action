# K-Scene2Action 개발 지침

## Codex만 사용

- 이 프로젝트의 AI 도구는 Codex만 사용한다. 구현, 코드 리뷰, 검증, 문서 작성과 서브에이전트 위임 모두에 적용한다.
- Claude, Gemini, Cursor, Cline 등 다른 AI 도구나 코딩 에이전트를 설치·설정·실행·호출하거나 작업을 위임하지 않는다.
- `CLAUDE.md`, `GEMINI.md`, `.cursor/` 등 다른 AI 도구용 설정 파일을 생성하거나 유지하지 않는다.
- AWS를 비롯한 설치 도구가 여러 AI 도구를 자동 감지하더라도 Codex에 필요한 설정만 적용한다. 아래 AWS 공통 지침보다 이 프로젝트의 Codex 전용 규칙을 우선한다.
- 필터 개발 코드 리뷰용 `gpt-6-luna` / `max`는 Codex 내부 서브에이전트로 사용한다.
- 일반 편집기, 터미널, Git, 테스트 도구와 AWS CLI는 사용할 수 있으며, 해당 도구의 타 AI 보조 기능은 사용하지 않는다.

## 필수 서브에이전트 코드 리뷰

이 저장소에서 작업하는 구현 담당 에이전트는 다음 절차를 MUST 준수한다.
이 규칙은 서브에이전트 리뷰를 실행하라는 명시적인 프로젝트 지시다.

### 적용 범위와 역할

- 코드, 테스트, 의존성, 실행 설정, 배포 설정, 안전 정책을 변경하면 작업 완료 보고 전에 반드시 별도의 리뷰 서브에이전트를 실행한다.
- 이 리뷰 규칙 자체를 변경할 때도 서브에이전트 리뷰를 거친다. 일반 설명 문서나 오탈자만 수정한 경우는 필수 대상에서 제외한다.
- 리뷰어는 해당 변경을 작성하지 않은 에이전트여야 한다. 구현 담당자의 자체 점검은 독립 리뷰를 대체할 수 없다.
- 리뷰어에게 읽기 전용 역할을 명시한다. 리뷰어는 파일 수정, 커밋, 배포, 실제 로봇 구동을 수행하지 않는다.
- 리뷰 서브에이전트는 추가 리뷰어를 생성하지 않는다. 리뷰 요청과 수정, 재검토 조율은 구현 담당자가 맡는다.

### 리뷰 모델과 추론 설정

- 필터 개발에 관한 코드 리뷰 서브에이전트만 반드시 `gpt-6-luna` 모델과 `max` 추론 수준을 사용한다. 최초 리뷰와 재검토 모두에 적용한다.
- 필터 개발에는 F1·F2·F3 및 관련 입력·출력 검사, 작업 계약·안전 정책 검증, 실행 허가·차단 경로와 이를 지원하는 테스트·의존성·실행 설정·배포 설정 변경이 포함된다. 다른 변경과 섞여 있어도 필터 관련 변경을 검토하는 리뷰어에게는 이 모델·추론 설정을 적용한다.
- 필터 개발 코드 리뷰어 생성 시 `model="gpt-6-luna"`, `reasoning_effort="max"`를 명시한다. 모델 재정의를 지원하도록 `fork_turns="none"`으로 생성하고 필요한 요구사항과 검토 범위를 직접 전달한다.
- 필터 개발 코드 리뷰에서 해당 설정을 사용할 수 없으면 다른 모델이나 추론 수준으로 임의 대체하지 않는다. 제한 사유와 리뷰 미완료 상태를 보고하고 대체 설정은 사용자의 명시적인 지시를 따른다.
- 필터 개발 외 변경도 앞의 ‘적용 범위와 역할’에 따른 리뷰 대상이면 독립 서브에이전트 리뷰는 필수지만, `gpt-6-luna` / `max` 지정은 적용하지 않는다. 해당 리뷰는 현재 세션의 모델·추론 설정을 기본으로 사용한다.
- 최종 리뷰 보고에는 리뷰어 식별자와 함께 실제 생성 요청에 사용한 모델·추론 설정을 기록한다.

### 필수 진행 순서

1. 구현 담당자는 변경을 마치고 변경에 필요한 검증을 수행한다.
2. 리뷰어에게 사용자 요구사항, 작업 경로, 변경 파일 목록, 비교 기준, 검증 결과와 알려진 제약을 전달한다. 미추적 파일도 포함한다. 첫 커밋 전이라 비교 기준이 없으면 그 사실을 밝히고 대상 파일 전체를 검토하게 한다.
3. 리뷰어는 실제 변경 내용과 관련 호출 경로를 직접 확인한다. 구현 담당자의 설명만으로 승인하지 않는다.
4. 리뷰 중에는 대상 파일을 수정하지 않는다. 리뷰 이후 변경한 부분과 영향을 받는 경로는 재검토를 요청한다.
5. 구현 담당자는 지적 사항을 확인하고 유효한 문제를 수정한다. 지적을 채택하지 않으면 코드나 검증 근거를 기록한다.
6. 수정한 경우 필요한 검증을 다시 수행하고, 리뷰어에게 수정 부분과 영향 범위의 재검토를 요청한다.
7. 최종 변경 상태에 대한 리뷰 결과를 받은 뒤에만 완료를 보고한다. 검증 통과만으로 리뷰 완료를 대신하지 않는다.

### 리뷰 우선순위

- 기능 정확성, 회귀, 실패 처리, 보안 및 물리 안전에 영향을 주는 결함을 우선한다.
- F2·F3 차단, 보류 또는 예외 이후 제어기 명령이 전달되는 경로가 있는지 확인한다.
- VLM 출력이나 외부 입력이 작업 계약·안전 정책·실행 권한을 변경할 수 있는지 확인한다.
- 승인한 계획과 Adapter가 전개한 명령열의 대상·목적지·순서가 일치하고 재검증되는지 확인한다.
- 승인 이후 계획이나 관측이 변경되었을 때 재검증하는지 확인한다.
- 누락·만료된 관측, 잘못된 ID, NaN·무한대, 좌표계·단위 불일치를 처리하는지 확인한다.
- 중복 요청·재시도가 동작을 중복 실행하거나, 정지 후 대기 명령이 실행되는지 확인한다.
- 모의 데이터와 개발용 우회 설정이 실제 실행에 섞이지 않는지 확인한다.
- 비밀정보 노출과 변경된 실패 조건에 대한 검증 누락을 확인한다.
- 추측이나 스타일 선호만으로 결함을 만들지 않는다. 문제가 없으면 지적 사항 없음으로 보고한다.

### 판정과 완료 조건

- 각 지적에는 심각도(P0~P3), 파일·줄 위치, 발생 조건, 영향, 근거와 수정 방향을 포함한다.
- P0는 즉각적인 중대 위해·손실, P1은 중대한 안전·보안·기능 결함, P2는 일반 기능·회귀 결함, P3는 낮은 영향의 개선 사항으로 분류한다.
- 유효한 P0·P1은 해결 전 완료·병합·배포하지 않는다. P2는 수정하거나 미해결 이유와 영향을 사용자에게 명시한다. P3는 선택적으로 반영한다.
- 최종 보고에는 리뷰어 식별자, 검토 범위, 지적 사항과 처리 결과, 수행한 검증, 남은 제약을 짧게 포함한다.
- 리뷰 도구를 사용할 수 없거나 리뷰어가 실패하면 리뷰 미완료로 보고한다. 자체 리뷰로 대체한 뒤 독립 리뷰가 완료됐다고 주장하지 않는다.
- 동일한 문제가 수정·재검토 두 차례에도 해결되지 않으면 반복을 멈추고 현재 결과와 미해결 원인을 보고한다. 필수 완료 조건을 충족하지 못한 상태를 완료로 표시하지 않는다.
- 이 규칙만으로 커밋, 푸시, 병합, 배포가 승인되는 것은 아니다. 해당 작업은 사용자가 요청한 범위를 따른다.

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance for the new AWS experience

This user has signed up for the new AWS experience. This experience lets you sign into AWS using a social provider and requires the following additional context.

Where this guidance conflicts with the project's own instructions, the project's instructions take precedence.

## Context

### Terminology:

- Say "project" instead of "account" — a project contains an AWS account and settings for sharing with other collaborators
- Say "team member" instead of "IAM user" — users are invited by email, not created or federated in IAM
- Say "AWS Settings" when referring to management tasks at [settings.aws.com](https://settings.aws.com/) (project management, billing, team members, spend limits). Users view their actual AWS resources in the AWS Management Console.
- Say "selected Region" when referring to the user's Region — not "home Region"
- The user has a managed IAM experience. This includes a managed service control policies (SCP) and resource control policies (RCP) that govern the use of AWS. They will still need to use IAM to create policies to let services work with each other. If there are questions about the SCPs or RCPs, go to the documentation at https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html

### Constraints:

- All projects share a single AWS Region determined by the user's contact address. Resources cannot be created in other Regions
- When developing:
  - MUST create all Regional resources in the project's assigned Region
  - You CAN create AWS WAF and Cloudwatch Logs resources in us-east-1 when there are global resources (like a global WAF instance) that require a connection to dependencies in us-east-1. You should not use these for any other reason, because resources in the selected Region will provide lower cost (due to no cross-Region traffic), increased availability (due to no cross-Region traffic), and easier manageability (due to not needing to look in another Region). When you need to do an inventory of resources, you need to look in both the selected Region and us-east-1 for Cloudwatch Logs or WAF resources.
  - MUST NOT attempt to create Lambda, API Gateway, or other Regional resources in any other Region
  - MUST direct users to confirm their Region in AWS Settings > View all projects > Overview > Additional Info > Region. If the user cannot confirm their Region, check in ~/.aws/config
  - MUST NOT use Lambda@Edge — excluded from both Lambda and CloudFront
  - MUST NOT use CloudFormation StackSets — no multi-account or multi-Region deployments
  - MUST NOT attempt cross-Region actions — no cross-Region replication for DynamoDB/S3/RDS, no multi-Region KMS keys
  - MUST NOT use Route 53 cross-Region routing — geolocation, latency-based, and failover routing policies are not available
  - CloudFront is a global service and its actions ARE allowed in `us-east-1`. A user can create a CloudFront distribution pointing to their project-region Lambda function URL or API Gateway. However, Lambda and API Gateway themselves MUST NOT be created in `us-east-1` — they must be in the project Region.
  - Reduced availability in `eu-north-1` specifically: Amazon Rekognition, Amazon Textract, Amazon Personalize, AWS App Runner are not available in that Region.
- IAM permissions for human access are managed by AWS. Don't assign roles to team members unless absolutely necessary
- The user may have a spend limit if they are on the paid plan. The limit that pauses their project if it's exceeded. If resources suddenly become inaccessible, ask if they have a spend limit configured. Only project owners can modify a spend limit.
- When developing:
  - MUST ask about spend limit status if the user reports sudden "Access Denied" errors on operations that previously worked
  - MUST direct users to check spend status in AWS Settings > Billing
  - MUST check if a user has upgraded their account to the paid plan
  - MUST ask the user if they want to clean up the successfully created resources or keep them to reduce cost
- The user sets up billing, creates spend limits, and retrieves and pays invoices in AWS Settings. The user creates budgets and optimizes their costs in the AWS Billing and Cost Management console
- Not all AWS services are available. If a service isn't working, do the following:
  1. Run the command `aws freetier get-account-plan-state`
  2. If accountPlanType": "FREE", check the [Free Tier supported services list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#supported-services-free-tier) next,
  3. If accountPlanType": "PAID", check the [Paid Tier supported services list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#supported-services-paid-plan).
  4. If neither list shows the service, check the [Not supported for this experience list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#unsupported-services). The user will need to activate advanced features to access this service.
- Users can activate advanced AWS services and capabilities for their account.
- Before starting a task, check whether a relevant AWS skill is available. Load the skill with retrieve_skill and prefer its guidance over general knowledge.

### Help level

- help_level (required): LOW, MEDIUM, or HIGH. While a user is building, you MUST ask the user: "How much guidance would you like from me? Low (I only flag security risks), medium (I ask a couple of clarifying questions if something seems off), or high (I explain what I'm doing, suggest alternatives, and flag best practices)."

You CAN update this rule file to save a user's help_level.

Constraints for each level:

**LOW:**

- MUST follow all constraints in this context file
- MUST execute the user’s request without modification
- MUST NOT ask clarifying questions unless the action would create a security vulnerability
- MUST NOT suggest alternatives or improvements

**MEDIUM:**

- MUST execute the user's request
- MAY ask up to two clarifying questions per task if the request has an ambiguity or a potential issue
- MUST NOT repeat a question or suggestion the user has already dismissed
- MUST NOT explain trade-offs or alternatives unless the user asks

**HIGH:**

- MUST explain what each step does and why before executing it
- MUST suggest alternatives when a better approach exists
- MUST flag best practices and explain trade-offs
- MUST still execute the user's choice if they disagree with a suggestion

<!-- END AWS Agent Toolkit rules -->
