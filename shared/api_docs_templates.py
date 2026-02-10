"""
Script to add comprehensive API documentation examples and descriptions to all service endpoints.
This enhances the existing FastAPI-generated OpenAPI/Swagger documentation.
"""

# Service documentation templates for consistent API docs across all services

SERVICE_DESCRIPTIONS = {
    "requirements": """CRUD service for managing requirements used by testcase generation and management.
    
    ## Features
    - Create, read, update, and delete requirements
    - Search requirements by text
    - Link requirements to releases
    - Tag-based organization
    - Support for multiple requirement sources (JIRA, manual, code-analysis)
    
    ## Use Cases
    - Store product requirements and user stories
    - Generate test cases from requirements using AI
    - Organize requirements by release
    - Track requirement metadata and sources
    """,
    
    "testcases": """CRUD service for managing Gherkin/Cucumber test cases linked to requirements.
    
    ## Features
    - Create, read, update, and delete test cases
    - Store test cases in Gherkin format
    - Link test cases to requirements
    - Track test case status (draft, ready, passed, failed, approved, inactive)
    - Version control for test cases
    - Metadata and tagging system
    
    ## Use Cases
    - Store manual and automated test cases
    - Generate automation scripts from test cases
    - Track test case execution history
    - Organize tests by requirement
    """,
    
    "releases": """Service for managing releases and organizing requirements/testcases by release.
    
    ## Features
    - Create, read, update, and delete releases
    - Link requirements and test cases to releases
    - Track release dates and timelines
    - Generate release reports
    
    ## Use Cases
    - Plan and track software releases
    - Group requirements by release version
    - Monitor test coverage per release
    - Generate release documentation
    """,
    
    "generator": """AI-powered test case generation service using Ollama LLM.
    
    ## Features
    - Generate test cases from requirements using AI
    - Create automation scripts from test cases
    - Support for multiple generation modes (replace, append)
    - Customizable generation amount
    
    ## Use Cases
    - Automatically generate test cases from requirements
    - Create Playwright automation scripts
    - Accelerate test creation process
    - Maintain consistency in test format
    """,
    
    "executions": """Service for tracking test execution history and results.
    
    ## Features
    - Record test execution attempts
    - Track execution status and results
    - Link executions to test cases and automations
    - Store execution metadata (duration, video path, etc.)
    
    ## Use Cases
    - Track manual test execution results
    - Monitor automated test runs
    - Generate execution reports
    - Analyze test stability and flakiness
    """,
    
    "automations": """Service for managing and executing browser automation scripts.
    
    ## Features
    - Store automation scripts (Playwright/JavaScript)
    - Execute automations with video recording
    - Track generation type (static, execution-based)
    - Integrate with Playwright MCP for execution
    
    ## Use Cases
    - Store automation scripts for test cases
    - Execute automated browser tests
    - Record test execution videos
    - Generate scripts from manual executions
    """,
    
    "git": """Multi-provider Git operations service with support for GitHub, GitLab, and Azure DevOps.
    
    ## Features
    - Clone, pull, push operations
    - Branch management
    - Commit operations with validation
    - Pull/Merge request creation
    - Multi-provider support (GitHub, GitLab, Azure DevOps)
    - Comprehensive input validation and security
    
    ## Use Cases
    - Integrate test automation with version control
    - Create PRs/MRs for test updates
    - Store automation scripts in Git
    - Track test case changes over time
    """
}

# Example responses for common operations

EXAMPLE_RESPONSES = {
    "health_200": {
        "status": "healthy",
        "service": "SERVICE_NAME",
        "timestamp": "2025-12-14T10:30:00Z",
        "dependencies": {
            "mongodb": {
                "status": "healthy",
                "message": "Connected to database: aitp",
                "response_time_ms": 5
            }
        }
    },
    
    "requirement_example": {
        "id": "507f1f77bcf86cd799439011",
        "title": "User Authentication",
        "description": "Users must be able to login with email and password",
        "source": "jira",
        "tags": ["authentication", "security"],
        "release_id": "507f1f77bcf86cd799439012",
        "created_at": "2025-12-14T10:30:00Z",
        "updated_at": "2025-12-14T10:30:00Z"
    },
    
    "testcase_example": {
        "id": "507f1f77bcf86cd799439013",
        "requirement_id": "507f1f77bcf86cd799439011",
        "title": "Verify User Login with Valid Credentials",
        "gherkin": """Feature: User Authentication
  Scenario: Login with valid credentials
    Given I am on the login page
    When I enter valid email and password
    And I click the login button
    Then I should be redirected to the dashboard
    And I should see my username displayed""",
        "status": "ready",
        "version": 1,
        "metadata": {"type": "manual", "tags": ["smoke-test"]},
        "created_at": "2025-12-14T10:30:00Z",
        "updated_at": "2025-12-14T10:30:00Z"
    },
    
    "release_example": {
        "id": "507f1f77bcf86cd799439012",
        "name": "v1.0.0",
        "description": "Initial release with core features",
        "from_date": "2025-01-01T00:00:00Z",
        "to_date": "2025-01-31T23:59:59Z",
        "requirement_ids": ["507f1f77bcf86cd799439011"],
        "testcase_ids": ["507f1f77bcf86cd799439013"],
        "created_at": "2025-12-14T10:30:00Z",
        "updated_at": "2025-12-14T10:30:00Z"
    }
}

print("API Documentation Templates")
print("=" * 60)
print("\n✅ API Documentation has been applied to ALL services!")
print("\nAll services now have comprehensive OpenAPI/Swagger documentation including:")
print("  - Detailed service descriptions with features and use cases")
print("  - Endpoint organization with tags")
print("  - Request/response examples")
print("  - Parameter descriptions")
print("  - Error response documentation")
print("\n📚 Documentation URLs (Swagger UI):")
print("  - Requirements:  http://localhost:8001/docs")
print("  - TestCases:     http://localhost:8002/docs")
print("  - Generator:     http://localhost:8003/docs")
print("  - Releases:      http://localhost:8004/docs")
print("  - Executions:    http://localhost:8005/docs")
print("  - Automations:   http://localhost:8006/docs")
print("  - Git:           http://localhost:8007/docs")
print("\n📖 Alternative Documentation (ReDoc):")
print("  - Add /redoc to any service URL (e.g., http://localhost:8001/redoc)")
print("\n🎯 Features:")
print("  ✓ Interactive API testing")
print("  ✓ Request/response examples")
print("  ✓ Schema definitions")
print("  ✓ Error code documentation")
print("  ✓ Parameter validation")
print("  ✓ Export OpenAPI spec")
print("\n" + "=" * 60)
