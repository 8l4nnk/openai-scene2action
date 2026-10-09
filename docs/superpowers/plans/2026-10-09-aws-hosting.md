# AWS dashboard hosting

Goal: Deploy the existing workbench at an authenticated HTTPS address in ap-southeast-2.

Architecture: One EC2 instance preserves the in-process controller and SQLite database on encrypted EBS. CloudFront uses a VPC origin to access the instance privately. Nginx forwards to one loopback Uvicorn worker. A separate hosted gateway authenticates every dashboard/API request before the existing loopback boundary. Local startup and safety engine remain unchanged.

- Add hosted-only password login, signed expiring HttpOnly/Secure/SameSite cookies, host/origin checks and bounded login requests. Require strong server settings at startup.
- Add tests for unauthenticated requests, expiry/tampering, cross-origin mutations, rate limiting, valid simulation roundtrip and local-mode isolation.
- Add boot/run/bundle files. Ship only explicit source paths, never local records, .env, attack corpora or presentation files. Build Linux C++ on the instance and install locked dependencies.
- Validate and request gpt-6-luna/max read-only review before deployment.
- Create private encrypted artifact bucket, scoped instance role, EC2 security group, encrypted 20GB root volume, IMDSv2 and SSM management. No SSH ingress. Run t3.small with standard CPU credits.
- Add a VPC origin, managed SG ingress only, no-cache CloudFront policy and WAF rate limits. Use default CloudFront HTTPS domain.
- Verify unauthenticated access denied, login, public UI/API, native backend and simulation/stop behavior. Save deployment resources and screenshot; provide access file privately.

Regional resources stay in ap-southeast-2; CloudFront/global WAF API operations use us-east-1. Current project is FREE/ACTIVE with USD100 credit. Keep resources running for the requested demo; record cleanup instructions. Optional OpenRouter runtime key goes only to private encrypted runtime configuration, with approval before copying it.

This is a 2D workbench deployment. Isaac GPU execution is a separate environment.
