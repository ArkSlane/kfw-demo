## 🟣 Future Ideas (Not Scheduled)

### Research & Exploration

- [ ] **AI Test Maintenance**
  - Detect UI changes and suggest script updates
  - Auto-update selectors when possible
  - ML model trained on historical test data

- [ ] **Natural Language Test Execution**
  - "Run all login tests"
  - "Show me failing tests from yesterday"
  - "Generate tests for user registration"

- [ ] **Smart Test Selection**
  - Only run tests affected by code changes
  - Use git diff to determine impact
  - ML-based prediction of relevant tests

- [ ] **Locator Injection & Stable Locators (data-testid)**
  - Scan merge requests or UI-selected files to suggest `data-testid` / `data-test-id` attributes
  - Recommend replacing brittle CSS/class-name selectors with stable test IDs
  - Optionally generate a patch/PR that injects missing test IDs into frontend components
  - Track adoption (coverage of elements with test IDs) and show progress over time

- [ ] **Test Suggestions for Merge Requests**
  - Detect new/changed functionality from merge request diffs
  - Suggest new tests (or updates) required to cover the change
  - Map code changes → impacted user journeys → candidate test cases
  - Highlight missing coverage before merge

- [ ] **AI Insights: Test Coverage Overview**
  - Show feature/requirement coverage by test cases + automations
  - Identify untested requirements/releases and “false confidence” (tests that don’t assert outcomes)
  - Provide “coverage gaps” recommendations and prioritize by risk/impact

- [ ] **AI Insights: Test Case Quality & Robustness**
  - Flag brittle selectors (class names, deep DOM paths) and recommend `data-testid` usage
  - Flag hardcoded data (credentials, emails) and suggest variable/test-data management
  - Detect missing assertions (no explicit success/error criteria) and recommend concrete checks
  - Detect weak/absent input validation (e.g., email format) and suggest validation test cases
  - Suggest dynamic locator strategies for dynamic content (lists, repeated elements)
  - Identify limited negative/edge-case coverage and propose additional scenarios

- [ ] **Visual Regression Testing**
  - Capture screenshots during execution
  - Compare with baseline images
  - Flag visual differences

- [ ] **Load Testing Integration**
  - Generate load test scripts from automations
  - Use K6, JMeter, or Locust
  - Automated performance regression detection

- [ ] **Load Testing via MCP**
  - Add an MCP server/tooling layer for load testing orchestration
  - Support scenario-based load runs triggered from the platform
  - Capture performance metrics + thresholds and store results alongside executions
  - Optional adapters: k6/Locust/JMeter runners behind a consistent MCP tool API

### Integration Ideas

- [ ] **JIRA Integration**
  - Sync requirements from JIRA issues
  - Update JIRA with test results
  - Link test cases to tickets

---

## 🛑 Blocked / Needs Discussion

- [ ] **Authentication Strategy**: JWT vs OAuth2 vs API Keys?
  - Need to decide on auth method
  - Consider multi-tenancy requirements
  - Plan user management approach

- [ ] **Cloud Deployment**: AWS vs Azure vs GCP?
  - Evaluate hosting options
  - Consider cost and scalability
  - Plan migration strategy

- [ ] **Video Storage**: Local volume vs S3/Cloud Storage?
  - Current: Docker volume (limited)
  - Future: May need cloud storage
  - Consider CDN for delivery

- [ ] **LLM Provider**: Continue with Ollama or add cloud LLMs?
  - Ollama: Free, private, self-hosted
  - Cloud (OpenAI, Anthropic): Better quality, paid
  - Hybrid approach?

- [ ] **Knowledge Graph for Testing Context**
  - Model relationships between releases, requirements, test cases, automations, and environments
  - Include entities like RK/IA/TOAB (and define canonical meaning + schema)
  - Use the graph to improve navigation, impact analysis, and LLM context
  - Power overview dashboards: “what gets tested”, “what changed”, “where are the gaps”

---

## 🐛 Known Bugs

### Critical

- [x] **Video files occasionally 0 bytes**
  - Issue: Context closes before video finalized
  - Attempted fix: Retry loop with 4-second wait
  - Status: Monitoring if fix is sufficient
  - Location: `services/playwright-mcp-agent/server.js` and `services/ollama-mcp-agent/server.js`

### Medium

- [ ] **Long automation scripts timeout**
  - Issue: 5-minute timeout too short for complex tests
  - Workaround: Increase timeout in httpx client
  - Solution: Make timeout configurable per automation
  - Location: `services/automations/main.py:168`

- [ ] **Git clone fails for large repos**
  - Issue: Timeout during clone of repos > 1GB
  - Workaround: Manual clone in container
  - Solution: Increase timeout, add progress tracking
  - Location: `services/git/main.py:159`

### Low

- [ ] **Branch list includes remote refs**
  - Issue: `remotes/origin/...` included in branch list
  - Impact: Minor UI clutter
  - Solution: Filter remote refs or separate local/remote
  - Location: `services/git/main.py:378`

- [ ] **Markdown code blocks in generated scripts**
  - Issue: Ollama sometimes returns ```javascript``` wrappers
  - Impact: Script execution fails
  - Current fix: Strip markdown blocks in parser
  - Status: Working but could be more robust
  - Location: `services/generator/main.py:138-145`

---

## 💡 Quick Wins (Low Effort, High Impact)

- [ ] **Add Loading Indicators**: Show spinner during long operations
- [ ] **Better Error Messages**: More helpful error descriptions
- [ ] **Keyboard Shortcuts**: Common actions in frontend
- [ ] **Dark Mode**: Toggle in frontend settings
- [ ] **Export Test Results**: Download as JSON/CSV
- [ ] **Copy Button**: Copy automation script to clipboard
- [ ] **Last Execution Timestamp**: Show when automation last ran
- [ ] **Quick Filter**: Filter test cases by status/tag
- [ ] **Breadcrumbs**: Navigation breadcrumbs in frontend
- [ ] **Tooltips**: Helpful hints on UI elements

