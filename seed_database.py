"""
Seed script to populate MongoDB with baseline test data.

Creates:
- 3 releases
- 5 requirements per release (15 total)
- 1-2 test cases per requirement (manual or automated)
"""
import asyncio
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import random

# MongoDB connection
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "aitp"  # Must match docker-compose DB_NAME

# Collections
RELEASES_COL = "releases"
REQUIREMENTS_COL = "requirements"
TESTCASES_COL = "testcases"


async def clear_collections(db):
    """Clear existing data (optional - comment out to keep existing data)."""
    print("Clearing existing data...")
    await db[RELEASES_COL].delete_many({})
    await db[REQUIREMENTS_COL].delete_many({})
    await db[TESTCASES_COL].delete_many({})
    print("✓ Collections cleared")


async def create_releases(db):
    """Create 3 sample releases."""
    print("\nCreating releases...")
    
    releases = [
        {
            "name": "v1.0.0 - Initial Release",
            "description": "First production release with core features including user authentication, dashboard, and basic reporting.",
            "from_date": datetime(2025, 2, 1, tzinfo=timezone.utc),
            "to_date": datetime(2025, 2, 28, tzinfo=timezone.utc),
            "requirement_ids": [],
            "testcase_ids": [],
            "created_at": datetime.now(timezone.utc) - timedelta(days=90),
            "updated_at": datetime.now(timezone.utc) - timedelta(days=30),
        },
        {
            "name": "v1.1.0 - Feature Enhancement",
            "description": "Enhanced features including advanced search, bulk operations, and performance improvements.",
            "from_date": datetime(2025, 5, 1, tzinfo=timezone.utc),
            "to_date": datetime(2025, 6, 15, tzinfo=timezone.utc),
            "requirement_ids": [],
            "testcase_ids": [],
            "created_at": datetime.now(timezone.utc) - timedelta(days=60),
            "updated_at": datetime.now(timezone.utc) - timedelta(days=10),
        },
        {
            "name": "v2.0.0 - Major Upgrade",
            "description": "Major architectural improvements with microservices, real-time updates, and AI-powered features.",
            "from_date": datetime(2025, 10, 1, tzinfo=timezone.utc),
            "to_date": datetime(2025, 12, 31, tzinfo=timezone.utc),
            "requirement_ids": [],
            "testcase_ids": [],
            "created_at": datetime.now(timezone.utc) - timedelta(days=30),
            "updated_at": datetime.now(timezone.utc) - timedelta(days=1),
        },
    ]
    
    result = await db[RELEASES_COL].insert_many(releases)
    release_ids = [str(id) for id in result.inserted_ids]
    
    print(f"✓ Created {len(release_ids)} releases")
    return release_ids, result.inserted_ids


async def create_requirements(db, release_ids, release_object_ids):
    """Create 5 requirements for each release."""
    print("\nCreating requirements...")
    
    requirement_templates = [
        # v1.0.0 requirements
        [
            {
                "title": "User Authentication System",
                "description": "Users must be able to register, login, and logout securely using email and password. Password must be hashed and stored securely.",
                "source": "manual",
                "tags": ["authentication", "security", "user-management"],
            },
            {
                "title": "Dashboard Overview",
                "description": "Dashboard should display key metrics including total test cases, pass/fail rate, recent executions, and upcoming releases.",
                "source": "manual",
                "tags": ["dashboard", "ui", "analytics"],
            },
            {
                "title": "Basic Test Case Management",
                "description": "Users should be able to create, read, update, and delete test cases with title, description, and steps.",
                "source": "manual",
                "tags": ["testcases", "crud", "core"],
            },
            {
                "title": "Manual Test Execution",
                "description": "Users must be able to execute test cases manually and record results (pass/fail/blocked) with comments.",
                "source": "manual",
                "tags": ["execution", "manual-testing", "results"],
            },
            {
                "title": "Basic Reporting",
                "description": "Generate simple reports showing test execution summary with pass/fail counts and execution history.",
                "source": "manual",
                "tags": ["reporting", "analytics", "export"],
            },
        ],
        # v1.1.0 requirements
        [
            {
                "title": "Advanced Search Functionality",
                "description": "Implement full-text search across test cases, requirements, and releases with filters for tags, status, and date ranges.",
                "source": "jira",
                "tags": ["search", "filters", "performance"],
            },
            {
                "title": "Bulk Operations",
                "description": "Support bulk actions for test cases including bulk update, delete, tag assignment, and export.",
                "source": "jira",
                "tags": ["bulk-operations", "efficiency", "ui"],
            },
            {
                "title": "Test Case Versioning",
                "description": "Track changes to test cases over time with version history and ability to revert to previous versions.",
                "source": "jira",
                "tags": ["versioning", "history", "audit"],
            },
            {
                "title": "Performance Optimization",
                "description": "Optimize database queries and API response times. Target: <200ms for list endpoints, <50ms for get endpoints.",
                "source": "code-analysis",
                "tags": ["performance", "optimization", "backend"],
            },
            {
                "title": "Email Notifications",
                "description": "Send email notifications for test execution completion, failed tests, and release updates.",
                "source": "jira",
                "tags": ["notifications", "email", "alerts"],
            },
        ],
        # v2.0.0 requirements
        [
            {
                "title": "Microservices Architecture",
                "description": "Refactor monolithic application into microservices for releases, requirements, testcases, and execution services.",
                "source": "code-analysis",
                "tags": ["architecture", "microservices", "scalability"],
            },
            {
                "title": "Real-time Collaboration",
                "description": "Enable real-time updates using WebSockets so multiple users can see live changes to test cases and executions.",
                "source": "manual",
                "tags": ["realtime", "websockets", "collaboration"],
            },
            {
                "title": "AI-Powered Test Generation",
                "description": "Use AI/LLM to automatically generate test cases from requirements with intelligent step suggestions.",
                "source": "manual",
                "tags": ["ai", "automation", "llm", "test-generation"],
            },
            {
                "title": "CI/CD Integration",
                "description": "Integrate with GitHub Actions, GitLab CI, and Jenkins for automated test execution on code changes.",
                "source": "jira",
                "tags": ["ci-cd", "automation", "integration"],
            },
            {
                "title": "Advanced Analytics Dashboard",
                "description": "Comprehensive analytics with trends, charts, test coverage heatmaps, and predictive insights using ML.",
                "source": "manual",
                "tags": ["analytics", "ml", "visualization", "insights"],
            },
        ],
    ]
    
    all_requirements = []
    requirement_mapping = {}  # Map release_id to requirement_ids
    
    for i, (release_id, release_oid) in enumerate(zip(release_ids, release_object_ids)):
        requirement_mapping[release_id] = []
        
        for req_template in requirement_templates[i]:
            req = {
                **req_template,
                "release_id": release_id,
                "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(20, 80)),
                "updated_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 15)),
            }
            all_requirements.append(req)
    
    result = await db[REQUIREMENTS_COL].insert_many(all_requirements)
    requirement_ids = [str(id) for id in result.inserted_ids]
    requirement_object_ids = result.inserted_ids
    
    # Map requirement IDs back to releases
    idx = 0
    for release_id in release_ids:
        requirement_mapping[release_id] = requirement_ids[idx:idx+5]
        idx += 5
    
    # Update releases with requirement_ids
    for release_oid, release_id in zip(release_object_ids, release_ids):
        await db[RELEASES_COL].update_one(
            {"_id": release_oid},
            {"$set": {"requirement_ids": requirement_mapping[release_id]}}
        )
    
    print(f"✓ Created {len(requirement_ids)} requirements (5 per release)")
    return requirement_ids, requirement_object_ids, requirement_mapping


async def create_testcases(db, requirement_ids, requirement_object_ids, requirement_mapping, release_ids, release_object_ids):
    """Create 1-2 test cases per requirement (mix of manual and automated)."""
    print("\nCreating test cases...")
    
    test_types = ["manual", "automated"]
    statuses = ["active", "active", "active", "draft"]  # More active than draft
    
    testcase_templates = {
        "authentication": [
            {
                "title": "Verify User Registration with Valid Data",
                "gherkin": """Feature: User Registration
  Scenario: Register with valid credentials
    Given I am on the registration page
    When I enter a valid email address
    And I enter a password with min 8 chars, 1 uppercase, 1 number
    And I confirm the password
    And I click the Register button
    Then my account should be created successfully
    And I should be redirected to the dashboard""",
                "status": "ready",
                "metadata": {
                    "type": "manual",
                    "tags": ["smoke-test", "registration"],
                    "steps": [
                        {"step_number": 1, "action": "Navigate to the registration page", "expected_result": "Registration form is displayed"},
                        {"step_number": 2, "action": "Enter valid email address (e.g., test@example.com)", "expected_result": "Email field accepts input"},
                        {"step_number": 3, "action": "Enter password with minimum 8 characters, 1 uppercase, 1 number", "expected_result": "Password field accepts input"},
                        {"step_number": 4, "action": "Confirm password in confirmation field", "expected_result": "Confirmation field accepts matching password"},
                        {"step_number": 5, "action": "Click the Register button", "expected_result": "Account is created and success message appears"},
                        {"step_number": 6, "action": "Verify redirection to dashboard", "expected_result": "User is redirected to dashboard page"},
                    ]
                },
            },
            {
                "title": "Automated Login Flow Test",
                "gherkin": """Feature: User Login
  Scenario: Login with valid credentials
    Given I have valid user credentials
    When I submit the login form
    Then I should receive a session token
    And I should be redirected to the dashboard""",
                "status": "ready",
                "metadata": {
                    "type": "automated",
                    "tags": ["automated", "regression"],
                    "script": "automated_login_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Open login page", "expected_result": "Login form is visible"},
                        {"step_number": 2, "action": "Enter valid username", "expected_result": "Username field is populated"},
                        {"step_number": 3, "action": "Enter valid password", "expected_result": "Password field is populated"},
                        {"step_number": 4, "action": "Click Login button", "expected_result": "Login request is sent"},
                        {"step_number": 5, "action": "Verify session token received", "expected_result": "Session token is present in response"},
                        {"step_number": 6, "action": "Verify redirect to dashboard", "expected_result": "Dashboard URL is loaded"},
                    ]
                },
            },
        ],
        "dashboard": [
            {
                "title": "Dashboard Metrics Display",
                "gherkin": """Feature: Dashboard Display
  Scenario: View dashboard metrics
    Given I am logged in as a test user
    When I navigate to the dashboard
    Then I should see the total test cases count
    And I should see the pass/fail rate chart
    And I should see the recent executions list""",
                "status": "ready",
                "metadata": {
                    "type": "manual",
                    "tags": ["ui", "visual"],
                    "steps": [
                        {"step_number": 1, "action": "Log in with valid test user credentials", "expected_result": "User is authenticated"},
                        {"step_number": 2, "action": "Navigate to the dashboard page", "expected_result": "Dashboard is loaded"},
                        {"step_number": 3, "action": "Verify total test cases count is displayed", "expected_result": "Count widget shows accurate number"},
                        {"step_number": 4, "action": "Verify pass/fail rate chart is visible", "expected_result": "Chart displays pass/fail percentages"},
                        {"step_number": 5, "action": "Verify recent executions list is populated", "expected_result": "List shows recent test executions"},
                    ]
                },
            },
        ],
        "testcases": [
            {
                "title": "Create Test Case with Required Fields",
                "gherkin": """Feature: Test Case Management
  Scenario: Create new test case
    Given I am on the Test Cases page
    When I click 'New Test Case' button
    And I enter the title
    And I enter the description
    And I add test steps
    And I click Save
    Then the test case should be created
    And it should appear in the list""",
                "status": "ready",
                "metadata": {
                    "type": "manual",
                    "tags": ["crud", "core"],
                    "steps": [
                        {"step_number": 1, "action": "Navigate to Test Cases page", "expected_result": "Test cases list is displayed"},
                        {"step_number": 2, "action": "Click 'New Test Case' button", "expected_result": "Test case creation form opens"},
                        {"step_number": 3, "action": "Enter test case title", "expected_result": "Title field is populated"},
                        {"step_number": 4, "action": "Enter test case description", "expected_result": "Description field is populated"},
                        {"step_number": 5, "action": "Add test steps with actions and expected results", "expected_result": "Steps are added to the form"},
                        {"step_number": 6, "action": "Click Save button", "expected_result": "Test case is saved successfully"},
                        {"step_number": 7, "action": "Verify test case appears in the list", "expected_result": "New test case is visible in the list"},
                    ]
                },
            },
            {
                "title": "Automated CRUD Operations Test",
                "gherkin": """Feature: Test Case API
  Scenario: CRUD operations via API
    When I create a test case via API
    And I read the test case
    And I update the test case
    And I delete the test case
    Then all operations should return success status codes""",
                "status": "ready",
                "metadata": {
                    "type": "automated",
                    "tags": ["automated", "api"],
                    "script": "testcase_crud_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Send POST request to create test case", "expected_result": "201 status code returned"},
                        {"step_number": 2, "action": "Send GET request to read test case", "expected_result": "200 status code and test case data returned"},
                        {"step_number": 3, "action": "Send PUT request to update test case", "expected_result": "200 status code and updated data returned"},
                        {"step_number": 4, "action": "Send DELETE request to delete test case", "expected_result": "200 status code returned"},
                        {"step_number": 5, "action": "Verify test case no longer exists", "expected_result": "404 status code on subsequent GET request"},
                    ]
                },
            },
        ],
        "execution": [
            {
                "title": "Manual Test Execution Flow",
                "gherkin": """Feature: Test Execution
  Scenario: Execute test manually
    Given I have selected a test case
    When I click 'Execute' button
    And I follow the test steps
    And I mark each step as pass or fail
    And I add execution comments
    And I submit the result
    Then the execution should be recorded with all details""",
                "status": "ready",
                "metadata": {
                    "type": "manual",
                    "tags": ["execution", "workflow"],
                    "steps": [
                        {"step_number": 1, "action": "Select a test case from the list", "expected_result": "Test case details are displayed"},
                        {"step_number": 2, "action": "Click 'Execute' button", "expected_result": "Execution wizard opens"},
                        {"step_number": 3, "action": "Follow test steps and mark each step result", "expected_result": "Each step can be marked as passed/failed/blocked"},
                        {"step_number": 4, "action": "Add execution notes and defects found", "expected_result": "Notes field accepts input"},
                        {"step_number": 5, "action": "Submit the execution", "expected_result": "Execution record is saved to database"},
                    ]
                },
            },
        ],
        "reporting": [
            {
                "title": "Generate Test Execution Report",
                "gherkin": """Feature: Reporting
  Scenario: Generate execution report
    Given I am on the Reports section
    When I select a date range
    And I click Generate Report
    Then I should see pass/fail counts
    And I should be able to export to CSV""",
                "status": "ready",
                "metadata": {
                    "type": "manual",
                    "tags": ["reporting", "export"],
                    "steps": [
                        {"step_number": 1, "action": "Navigate to Reports section", "expected_result": "Reports interface is displayed"},
                        {"step_number": 2, "action": "Select start and end date for report", "expected_result": "Date range is selected"},
                        {"step_number": 3, "action": "Click 'Generate Report' button", "expected_result": "Report is generated"},
                        {"step_number": 4, "action": "Verify pass/fail counts are displayed", "expected_result": "Counts are shown correctly"},
                        {"step_number": 5, "action": "Click export to CSV button", "expected_result": "CSV file is downloaded"},
                    ]
                },
            },
            {
                "title": "Automated Report API Test",
                "gherkin": """Feature: Report API
  Scenario: Get report data via API
    When I call the report API with filters
    Then I should receive report data in JSON format""",
                "status": "ready",
                "metadata": {
                    "type": "automated",
                    "tags": ["automated", "api"],
                    "script": "report_api_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Send GET request to /reports endpoint with filters", "expected_result": "200 status code"},
                        {"step_number": 2, "action": "Verify response contains report data", "expected_result": "JSON with pass/fail metrics"},
                        {"step_number": 3, "action": "Validate response structure", "expected_result": "All required fields present"},
                    ]
                },
            },
        ],
        "search": [
            {
                "title": "Search Test Cases by Keyword",
                "gherkin": """Feature: Search
  Scenario: Search for test cases
    Given I am on the test cases page
    When I enter a search keyword
    And I press Enter
    Then I should see all matching test cases""",
                "status": "ready",
                "metadata": {
                    "type": "manual",
                    "tags": ["search", "ui"],
                    "steps": [
                        {"step_number": 1, "action": "Navigate to Test Cases page", "expected_result": "Test cases list is displayed"},
                        {"step_number": 2, "action": "Enter search keyword in search box", "expected_result": "Search box accepts input"},
                        {"step_number": 3, "action": "Press Enter or click Search button", "expected_result": "Search is executed"},
                        {"step_number": 4, "action": "Verify matching test cases are displayed", "expected_result": "Only relevant test cases are shown"},
                    ]
                },
            },
        ],
        "bulk-operations": [
            {
                "title": "Bulk Update Test Cases",
                "gherkin": """Feature: Bulk Operations
  Scenario: Update multiple test cases
    Given I have selected multiple test cases
    When I click 'Bulk Actions'
    And I select 'Update Tags'
    And I add a new tag
    And I confirm the action
    Then all selected test cases should have the new tag""",
                "status": "ready",
                "metadata": {
                    "type": "manual",
                    "tags": ["bulk", "efficiency"],
                    "steps": [
                        {"step_number": 1, "action": "Select multiple test cases using checkboxes", "expected_result": "Multiple test cases are selected"},
                        {"step_number": 2, "action": "Click 'Bulk Actions' dropdown", "expected_result": "Bulk actions menu is displayed"},
                        {"step_number": 3, "action": "Select 'Update Tags' option", "expected_result": "Tag update dialog opens"},
                        {"step_number": 4, "action": "Add a new tag and confirm", "expected_result": "Tag is added"},
                        {"step_number": 5, "action": "Verify all selected test cases have the new tag", "expected_result": "Tag appears on all selected items"},
                    ]
                },
            },
            {
                "title": "Automated Bulk Operations Test",
                "gherkin": """Feature: Bulk API
  Scenario: Bulk operations via API
    When I perform bulk update via API
    And I perform bulk delete via API
    Then all operations should complete successfully""",
                "status": "ready",
                "metadata": {
                    "type": "automated",
                    "tags": ["automated", "api"],
                    "script": "bulk_operations_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Send POST /bulk-update with test case IDs and updates", "expected_result": "200 status code"},
                        {"step_number": 2, "action": "Verify all test cases were updated", "expected_result": "All items reflect changes"},
                        {"step_number": 3, "action": "Send DELETE /bulk-delete with test case IDs", "expected_result": "200 status code"},
                        {"step_number": 4, "action": "Verify all test cases were deleted", "expected_result": "Items no longer exist"},
                    ]
                },
            },
        ],
        "versioning": [
            {
                "title": "Test Case Version History",
                "gherkin": """Feature: Version Control
  Scenario: Track version history
    Given I have an existing test case
    When I make changes to title and steps
    And I save the changes
    And I view version history
    Then I should see all previous versions
    And I should be able to revert to a previous version""",
                "status": "draft",
                "metadata": {
                    "type": "manual",
                    "tags": ["versioning", "audit"],
                    "steps": [
                        {"step_number": 1, "action": "Open an existing test case", "expected_result": "Test case details are displayed"},
                        {"step_number": 2, "action": "Edit title and steps", "expected_result": "Changes are made"},
                        {"step_number": 3, "action": "Save the changes", "expected_result": "New version is created"},
                        {"step_number": 4, "action": "Click 'View History' button", "expected_result": "Version history dialog opens"},
                        {"step_number": 5, "action": "Verify all previous versions are listed", "expected_result": "Version list is shown with timestamps"},
                        {"step_number": 6, "action": "Select a previous version and click 'Revert'", "expected_result": "Test case is restored to selected version"},
                    ]
                },
            },
        ],
        "performance": [
            {
                "title": "API Response Time Test",
                "gherkin": """Feature: Performance
  Scenario: Measure API response times
    When I send 100 concurrent requests
    Then list endpoints should respond in < 200ms
    And get endpoints should respond in < 50ms""",
                "status": "ready",
                "metadata": {
                    "type": "automated",
                    "tags": ["performance", "load-test"],
                    "script": "performance_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Send 100 concurrent requests to /list endpoint", "expected_result": "All requests complete"},
                        {"step_number": 2, "action": "Measure average response time for list endpoint", "expected_result": "Average < 200ms"},
                        {"step_number": 3, "action": "Send 100 concurrent requests to /get endpoint", "expected_result": "All requests complete"},
                        {"step_number": 4, "action": "Measure average response time for get endpoint", "expected_result": "Average < 50ms"},
                    ]
                },
            },
        ],
        "notifications": [
            {
                "title": "Email Notification on Test Failure",
                "gherkin": """Feature: Notifications
  Scenario: Send email on test failure
    Given I have executed a test case
    When I mark it as failed
    And I submit the result
    Then an email notification should be sent
    And it should contain failure details""",
                "status": "draft",
                "metadata": {
                    "type": "manual",
                    "tags": ["notifications", "integration"],
                    "steps": [
                        {"step_number": 1, "action": "Execute a test case and mark it as failed", "expected_result": "Test execution is recorded as failed"},
                        {"step_number": 2, "action": "Submit the execution result", "expected_result": "Execution is saved to database"},
                        {"step_number": 3, "action": "Check email inbox for notification", "expected_result": "Email is received within 1 minute"},
                        {"step_number": 4, "action": "Verify email contains test case name", "expected_result": "Test case name is in email body"},
                        {"step_number": 5, "action": "Verify email contains failure details", "expected_result": "Failure reason and steps are included"},
                    ]
                },
            },
        ],
        "microservices": [
            {
                "title": "Service Communication Test",
                "gherkin": """Feature: Microservices
  Scenario: Test inter-service communication
    When I send requests between services
    Then all services should communicate successfully
    And error handling should work properly""",
                "status": "draft",
                "metadata": {
                    "type": "automated",
                    "tags": ["microservices", "integration"],
                    "script": "service_integration_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Send request from Frontend to Requirements service", "expected_result": "200 response received"},
                        {"step_number": 2, "action": "Send request from Requirements to TestCases service", "expected_result": "Data is fetched successfully"},
                        {"step_number": 3, "action": "Verify all services can communicate", "expected_result": "No connection errors"},
                        {"step_number": 4, "action": "Test error handling by simulating service down", "expected_result": "Graceful error message displayed"},
                    ]
                },
            },
        ],
        "realtime": [
            {
                "title": "WebSocket Connection Test",
                "gherkin": """Feature: Real-time Updates
  Scenario: WebSocket connectivity
    When I establish a WebSocket connection
    Then I should receive real-time updates""",
                "status": "draft",
                "metadata": {
                    "type": "automated",
                    "tags": ["websockets", "realtime"],
                    "script": "websocket_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Connect to WebSocket endpoint", "expected_result": "Connection is established"},
                        {"step_number": 2, "action": "Subscribe to test execution updates", "expected_result": "Subscription confirmed"},
                        {"step_number": 3, "action": "Trigger a test execution from another session", "expected_result": "Update message is received in WebSocket"},
                        {"step_number": 4, "action": "Verify update contains correct data", "expected_result": "Test execution status is included"},
                    ]
                },
            },
        ],
        "ai": [
            {
                "title": "AI Test Case Generation from Requirement",
                "gherkin": """Feature: AI Test Generation
  Scenario: Generate tests from requirement
    Given I have opened a requirement
    When I click 'Generate Test Cases'
    Then AI should generate 3-5 relevant test cases
    And they should cover the requirement adequately""",
                "status": "draft",
                "metadata": {
                    "type": "manual",
                    "tags": ["ai", "automation"],
                    "steps": [
                        {"step_number": 1, "action": "Open a requirement detail page", "expected_result": "Requirement details are displayed"},
                        {"step_number": 2, "action": "Click 'Generate Test Cases' button", "expected_result": "AI generation dialog opens"},
                        {"step_number": 3, "action": "Confirm generation request", "expected_result": "AI starts generating test cases"},
                        {"step_number": 4, "action": "Wait for generation to complete", "expected_result": "3-5 test cases are generated"},
                        {"step_number": 5, "action": "Review generated test cases", "expected_result": "Test cases are relevant and comprehensive"},
                    ]
                },
            },
            {
                "title": "Automated AI API Integration Test",
                "gherkin": """Feature: AI API
  Scenario: Test AI service integration
    When I call the AI generation API
    Then it should return structured test case data""",
                "status": "draft",
                "metadata": {
                    "type": "automated",
                    "tags": ["ai", "api", "integration"],
                    "script": "ai_generation_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Send POST request to /generate endpoint", "expected_result": "Request is accepted"},
                        {"step_number": 2, "action": "Wait for generation to complete", "expected_result": "Response is received within timeout"},
                        {"step_number": 3, "action": "Verify response contains test cases array", "expected_result": "Array with test cases is returned"},
                        {"step_number": 4, "action": "Validate test case structure", "expected_result": "Each test case has required fields"},
                    ]
                },
            },
        ],
        "ci-cd": [
            {
                "title": "GitHub Actions Integration Test",
                "gherkin": """Feature: CI/CD Integration
  Scenario: Trigger tests via GitHub Actions
    When a pull request is created
    Then tests should execute automatically
    And results should be posted to the PR""",
                "status": "draft",
                "metadata": {
                    "type": "automated",
                    "tags": ["ci-cd", "github"],
                    "script": "github_actions_test.py",
                    "steps": [
                        {"step_number": 1, "action": "Create a pull request in GitHub", "expected_result": "PR is created successfully"},
                        {"step_number": 2, "action": "Verify GitHub Action is triggered", "expected_result": "Workflow starts automatically"},
                        {"step_number": 3, "action": "Wait for test execution to complete", "expected_result": "Tests run and complete"},
                        {"step_number": 4, "action": "Verify results are posted as PR comment", "expected_result": "Test results appear in PR"},
                    ]
                },
            },
        ],
        "analytics": [
            {
                "title": "Analytics Dashboard Load Test",
                "gherkin": """Feature: Advanced Analytics
  Scenario: Load analytics dashboard
    When I navigate to the Analytics page
    Then I should see trend charts
    And I should see heatmap visualizations
    And I should see predictive insights""",
                "status": "draft",
                "metadata": {
                    "type": "manual",
                    "tags": ["analytics", "visualization"],
                    "steps": [
                        {"step_number": 1, "action": "Navigate to Analytics page", "expected_result": "Analytics interface loads"},
                        {"step_number": 2, "action": "Verify trend charts are displayed", "expected_result": "Charts show test execution trends over time"},
                        {"step_number": 3, "action": "Verify heatmap visualizations", "expected_result": "Heatmap shows test activity patterns"},
                        {"step_number": 4, "action": "Verify predictive insights section", "expected_result": "AI-generated insights are displayed"},
                    ]
                },
            },
        ],
    }
    
    # Default template for requirements without specific test templates
    default_templates = [
        {
            "title": "Functional Test - {req_title}",
            "gherkin": """Feature: {req_title}
  Scenario: Basic functionality test
    Given the feature is implemented
    When I use the feature as described
    Then it should work as expected""",
            "status": "ready",
            "metadata": {
                "type": "manual",
                "tags": ["functional"],
                "steps": [
                    {"step_number": 1, "action": "Verify the feature is accessible", "expected_result": "Feature is available in the application"},
                    {"step_number": 2, "action": "Test the feature with valid inputs", "expected_result": "Feature responds as expected"},
                    {"step_number": 3, "action": "Verify output/result is correct", "expected_result": "Correct output is produced"},
                ]
            },
        },
        {
            "title": "API Test - {req_title}",
            "gherkin": """Feature: {req_title} API
  Scenario: API endpoint test
    When I call the API endpoint
    Then it should return expected responses""",
            "status": "ready",
            "metadata": {
                "type": "automated",
                "tags": ["api", "automated"],
                "steps": [
                    {"step_number": 1, "action": "Send API request with valid parameters", "expected_result": "Request is processed"},
                    {"step_number": 2, "action": "Verify response status code", "expected_result": "200 status code is returned"},
                    {"step_number": 3, "action": "Validate response body structure", "expected_result": "Response matches expected schema"},
                ]
            },
        },
    ]
    
    all_testcases = []
    testcase_mapping = {}  # Map requirement_id to testcase_ids
    release_testcases = {rid: [] for rid in release_ids}  # Map release_id to all testcase_ids
    
    requirements = await db[REQUIREMENTS_COL].find().to_list(length=100)
    
    for req in requirements:
        req_id = str(req["_id"])
        req_title = req["title"]
        req_tags = req.get("tags", [])
        release_id = req["release_id"]
        
        testcase_mapping[req_id] = []
        
        # Find matching templates based on tags
        matching_templates = []
        for tag in req_tags:
            if tag in testcase_templates:
                matching_templates.extend(testcase_templates[tag])
        
        # If no matching templates, use defaults
        if not matching_templates:
            matching_templates = default_templates
        
        # Create 1-2 test cases per requirement
        num_testcases = random.randint(1, 2)
        selected_templates = random.sample(matching_templates, min(num_testcases, len(matching_templates)))
        
        for template in selected_templates:
            # Customize template
            testcase = {
                "title": template["title"].format(req_title=req_title) if "{req_title}" in template["title"] else template["title"],
                "gherkin": template["gherkin"].format(req_title=req_title) if "{req_title}" in template["gherkin"] else template["gherkin"],
                "status": template["status"],
                "requirement_id": req_id,
                "version": 1,
                "metadata": template.get("metadata", {}),
                "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(10, 60)),
                "updated_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 10)),
            }
            all_testcases.append(testcase)
    
    result = await db[TESTCASES_COL].insert_many(all_testcases)
    testcase_ids = [str(id) for id in result.inserted_ids]
    
    # Map testcase IDs back to requirements and releases
    idx = 0
    for req in requirements:
        req_id = str(req["_id"])
        release_id = req["release_id"]
        
        # Find how many testcases were created for this requirement
        req_testcases = [tc for tc in all_testcases[idx:] if tc.get("requirement_id") == req_id]
        num_tc = len(req_testcases)
        
        testcase_mapping[req_id] = testcase_ids[idx:idx+num_tc]
        release_testcases[release_id].extend(testcase_ids[idx:idx+num_tc])
        idx += num_tc
        
        # Update requirement with testcase_ids (if field exists in schema)
        # await db[REQUIREMENTS_COL].update_one(
        #     {"_id": req["_id"]},
        #     {"$set": {"testcase_ids": testcase_mapping[req_id]}}
        # )
    
    # Update releases with all testcase_ids
    for release_oid, release_id in zip(release_object_ids, release_ids):
        await db[RELEASES_COL].update_one(
            {"_id": release_oid},
            {"$set": {"testcase_ids": release_testcases[release_id]}}
        )
    
    print(f"✓ Created {len(testcase_ids)} test cases (1-2 per requirement)")
    
    # Print statistics
    manual_count = sum(1 for tc in all_testcases if tc.get("metadata", {}).get("type") == "manual")
    automated_count = sum(1 for tc in all_testcases if tc.get("metadata", {}).get("type") == "automated")
    print(f"  - Manual: {manual_count}")
    print(f"  - Automated: {automated_count}")
    
    return testcase_ids


async def print_summary(db):
    """Print summary of created data."""
    print("\n" + "="*60)
    print("DATABASE SEEDING COMPLETE")
    print("="*60)
    
    releases = await db[RELEASES_COL].find().to_list(length=100)
    requirements = await db[REQUIREMENTS_COL].find().to_list(length=100)
    testcases = await db[TESTCASES_COL].find().to_list(length=100)
    
    print(f"\n📦 Total Records Created:")
    print(f"  - Releases: {len(releases)}")
    print(f"  - Requirements: {len(requirements)}")
    print(f"  - Test Cases: {len(testcases)}")
    
    print(f"\n🚀 Releases:")
    for release in releases:
        req_count = len(release.get("requirement_ids", []))
        tc_count = len(release.get("testcase_ids", []))
        print(f"  - {release['name']}")
        print(f"    └─ {req_count} requirements, {tc_count} test cases")
    
    print(f"\n📝 Requirements by Source:")
    sources = {}
    for req in requirements:
        source = req.get("source", "unknown")
        sources[source] = sources.get(source, 0) + 1
    for source, count in sources.items():
        print(f"  - {source}: {count}")
    
    print(f"\n🧪 Test Cases by Type:")
    manual = sum(1 for tc in testcases if tc.get("metadata", {}).get("type") == "manual")
    automated = sum(1 for tc in testcases if tc.get("metadata", {}).get("type") == "automated")
    print(f"  - Manual: {manual}")
    print(f"  - Automated: {automated}")
    
    print(f"\n✅ Database ready for testing!")
    print(f"   MongoDB: {MONGO_URI}")
    print(f"   Database: {DB_NAME}")
    print("="*60 + "\n")


async def main():
    """Main seeding function."""
    print("="*60)
    print("SEEDING AI TESTING DATABASE")
    print("="*60)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    
    try:
        # Test connection
        await client.admin.command('ping')
        print(f"✓ Connected to MongoDB at {MONGO_URI}")
        print(f"✓ Using database: {DB_NAME}\n")
        
        # Clear existing data (comment out to keep existing data)
        await clear_collections(db)
        
        # Create releases
        release_ids, release_object_ids = await create_releases(db)
        
        # Create requirements
        requirement_ids, requirement_object_ids, requirement_mapping = await create_requirements(
            db, release_ids, release_object_ids
        )
        
        # Create test cases
        testcase_ids = await create_testcases(
            db, requirement_ids, requirement_object_ids, 
            requirement_mapping, release_ids, release_object_ids
        )
        
        # Print summary
        await print_summary(db)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())

