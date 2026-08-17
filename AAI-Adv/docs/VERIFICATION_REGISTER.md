# Verification Register

| Confidence | Items |
|---|---|
| VERIFIED (executed) | agent-framework-core 1.14.0 workflow/HITL/checkpoint/middleware APIs; agent-framework-foundry 1.11.0 imports incl. FoundryChatClient.as_agent() (create_agent() does NOT exist); mcp 2.0.0 MCPServer + stdio client round trip; all 12 labs + capstone + 17 acceptance tests pass offline on Python 3.12. |
| VERIFIED (introspection only) | FoundryChatClient constructor (project_endpoint/model/credential); UsageDetails token keys; FileCheckpointStorage.list_checkpoints(workflow_name=...). |
| VERSION-SENSITIVE [VERIFY before delivery] | Foundry portal navigation (endpoint location, IQ index creation, evaluator registration, asset catalog, hosted model-router) — preview surfaces, re-check against learn.microsoft.com; Azure RBAC role name for Foundry data plane; vision/image content support per deployment; foundry evals API (FoundryEvals/evaluate_foundry_target) signatures. |
| NOT EXECUTED | Azure-mode paths end-to-end (no credentials in the build environment) — code paths are gated on env vars and follow verified constructor signatures, but live-run them during cohort prep; Python 3.14 execution; Bicep deployment to a real subscription. |
| ILLUSTRATIVE (labelled) | Token prices in Labs 2.4/capstone; all timing estimates. |

# Corrections Table

| # | Defect | Fix | Where |
|---|---|---|---|
| C1 | ctx.set_state called with a dict | API is set_state(key, value) | Lab 1.1 |
| C2 | await on set_state/get_state | Both are synchronous | Lab 1.1 |
| C3 | Tool.inputSchema attribute | mcp 2.0 renamed to input_schema | Lab 1.2 |
| C4 | PEP 563 future import breaks @response_handler validation | Remove `from __future__ import annotations` from executor modules | Lab 1.4, capstone |
| C5 | Retry loop never exercised (happy-path data) | Planted defect D6 (NW-1012, 8% promo) + assertion that it fires | Lab 2.1, data_gen |
| C6 | Injection regex allowed exactly one adjective; 'ignore all previous instructions' evaded it | Multi-adjective pattern; found by the benchmark's own safety gate | Lab 2.3 |
| C7 | Span-name equality assertion failed | agent-framework auto-emits invoke_agent spans; assert superset | Lab 2.4 |
| C8 | @chat_middleware on Agent never invoked with custom client; next(ctx) wrong | Use @agent_middleware; continuation is next() with no args; assert on captured model input | Lab 3.2 |
| C9 | list_checkpoints() missing workflow_name | Keyword-only arg matching the WorkflowBuilder name | Lab 3.4 |
| C10 | Asserted per-run post counts after resume | Assert END-STATE invariant: 24 unique ledger entries after replay + D3 dup | Lab 3.4 |
| C11 | Starters broke: parents[2] resolves wrong one directory deeper | Generator rewrites ROOT to an upward marker search | builders |
| C12 | UnicodeEncodeError on Windows: lab printed U+2714 checkmark; child stdout defaults to cp1252 | ASCII-only prints in labs; test runner forces PYTHONUTF8=1 for subprocesses. Found by first Windows execution | Lab 1.4, tests |
