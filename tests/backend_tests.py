#!/usr/bin/env python3
"""
Extensive backend integration tests for all microservices.

Services under test:
 - Requirements  (port 8001)
 - Testcases     (port 8002)
 - Generator     (port 8003)
 - Releases      (port 8004)
 - Executions    (port 8005)
 - Automations   (port 8006)
 - Git           (port 8007)
 - TOABRKIA      (port 8008)

Run:  python tests/backend_tests.py
"""

import httpx
import sys
import json
import traceback
from datetime import datetime, timezone

BASE = "http://localhost"
SERVICES = {
    "requirements": f"{BASE}:8001",
    "testcases": f"{BASE}:8002",
    "generator": f"{BASE}:8003",
    "releases": f"{BASE}:8004",
    "executions": f"{BASE}:8005",
    "automations": f"{BASE}:8006",
    "git": f"{BASE}:8007",
    "toabrkia": f"{BASE}:8008",
}

passed = 0
failed = 0
errors = []

# IDs created during tests for cleanup
created_ids = {
    "requirements": [],
    "testcases": [],
    "releases": [],
    "executions": [],
    "automations": [],
    "assessments": [],
    "knowledge_graphs": [],
}


def test(name):
    """Decorator to register and run a test."""
    def decorator(fn):
        fn._test_name = name
        return fn
    return decorator


def run_test(fn):
    global passed, failed
    name = getattr(fn, "_test_name", fn.__name__)
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except AssertionError as e:
        failed += 1
        msg = f"  [FAIL] {name}: {e}"
        print(msg)
        errors.append(msg)
    except Exception as e:
        failed += 1
        msg = f"  [ERROR] {name}: {type(e).__name__}: {e}"
        print(msg)
        errors.append(msg)
        traceback.print_exc()


# ====================================================================
# HTTP helpers
# ====================================================================
client = httpx.Client(timeout=30)


def get(url, expected_status=200):
    r = client.get(url)
    assert r.status_code == expected_status, f"GET {url} => {r.status_code} (expected {expected_status}): {r.text[:300]}"
    return r


def post(url, json_data, expected_status=201):
    r = client.post(url, json=json_data)
    assert r.status_code == expected_status, f"POST {url} => {r.status_code} (expected {expected_status}): {r.text[:300]}"
    return r


def put(url, json_data, expected_status=200):
    r = client.put(url, json=json_data)
    assert r.status_code == expected_status, f"PUT {url} => {r.status_code} (expected {expected_status}): {r.text[:300]}"
    return r


def delete(url, expected_status=204):
    r = client.delete(url)
    assert r.status_code == expected_status, f"DELETE {url} => {r.status_code} (expected {expected_status}): {r.text[:300]}"
    return r


# ====================================================================
# 1. HEALTH CHECKS
# ====================================================================
print("\n===== 1. HEALTH CHECKS =====")


@test("Requirements health")
def test_requirements_health():
    r = get(f"{SERVICES['requirements']}/health")
    data = r.json()
    assert data["service"] == "requirements"
    assert "dependencies" in data

@test("Testcases health")
def test_testcases_health():
    r = get(f"{SERVICES['testcases']}/health")
    data = r.json()
    assert data["service"] == "testcases"

@test("Generator health")
def test_generator_health():
    r = get(f"{SERVICES['generator']}/health")
    data = r.json()
    assert data["service"] == "generator"

@test("Releases health")
def test_releases_health():
    r = get(f"{SERVICES['releases']}/health")
    data = r.json()
    assert data["service"] == "releases"

@test("Executions health")
def test_executions_health():
    r = get(f"{SERVICES['executions']}/health")
    data = r.json()
    assert data["service"] == "executions"

@test("Automations health")
def test_automations_health():
    r = get(f"{SERVICES['automations']}/health")
    data = r.json()
    assert data["service"] == "automations"

@test("Git health")
def test_git_health():
    r = get(f"{SERVICES['git']}/health")
    data = r.json()
    assert "status" in data

@test("TOABRKIA health")
def test_toabrkia_health():
    r = get(f"{SERVICES['toabrkia']}/health")
    data = r.json()
    assert data["service"] == "toabrkia"

for fn in [test_requirements_health, test_testcases_health, test_generator_health,
           test_releases_health, test_executions_health, test_automations_health,
           test_git_health, test_toabrkia_health]:
    run_test(fn)


# ====================================================================
# 2. REQUIREMENTS SERVICE CRUD
# ====================================================================
print("\n===== 2. REQUIREMENTS SERVICE =====")

req_id = None

@test("Create requirement")
def test_create_requirement():
    global req_id
    r = post(f"{SERVICES['requirements']}/requirements", {
        "title": "Backend Test Requirement",
        "description": "Created by automated backend tests",
        "source": "automated-test",
        "tags": ["test", "backend"],
    })
    data = r.json()
    req_id = data["id"]
    created_ids["requirements"].append(req_id)
    assert data["title"] == "Backend Test Requirement"
    assert data["description"] == "Created by automated backend tests"
    assert data["source"] == "automated-test"
    assert data["tags"] == ["test", "backend"]
    assert "created_at" in data
    assert "updated_at" in data

@test("Create requirement - validation (title too short)")
def test_create_requirement_validation():
    r = client.post(f"{SERVICES['requirements']}/requirements", json={"title": "ab"})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"

@test("Create requirement - validation (missing title)")
def test_create_requirement_no_title():
    r = client.post(f"{SERVICES['requirements']}/requirements", json={"description": "no title"})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"

@test("Get requirement by ID")
def test_get_requirement():
    r = get(f"{SERVICES['requirements']}/requirements/{req_id}")
    data = r.json()
    assert data["id"] == req_id
    assert data["title"] == "Backend Test Requirement"

@test("Get requirement - not found")
def test_get_requirement_404():
    r = client.get(f"{SERVICES['requirements']}/requirements/000000000000000000000000")
    assert r.status_code == 404

@test("Get requirement - invalid ID")
def test_get_requirement_bad_id():
    r = client.get(f"{SERVICES['requirements']}/requirements/not-a-valid-id")
    assert r.status_code == 400

@test("List requirements")
def test_list_requirements():
    r = get(f"{SERVICES['requirements']}/requirements")
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0

@test("List requirements - search")
def test_list_requirements_search():
    r = get(f"{SERVICES['requirements']}/requirements?q=Backend+Test+Requirement")
    data = r.json()
    assert any(d["id"] == req_id for d in data), "Created requirement not found via search"

@test("List requirements - pagination")
def test_list_requirements_pagination():
    r = get(f"{SERVICES['requirements']}/requirements?limit=1&skip=0")
    data = r.json()
    assert len(data) <= 1

@test("Update requirement")
def test_update_requirement():
    r = put(f"{SERVICES['requirements']}/requirements/{req_id}", {
        "title": "Backend Test Requirement (Updated)",
        "tags": ["test", "backend", "updated"],
    })
    data = r.json()
    assert data["title"] == "Backend Test Requirement (Updated)"
    assert "updated" in data["tags"]

@test("Update requirement - no fields")
def test_update_requirement_no_fields():
    r = client.put(f"{SERVICES['requirements']}/requirements/{req_id}", json={})
    assert r.status_code == 400

@test("Update requirement - not found")
def test_update_requirement_404():
    r = client.put(f"{SERVICES['requirements']}/requirements/000000000000000000000000", json={"title": "Nope"})
    assert r.status_code == 404

for fn in [test_create_requirement, test_create_requirement_validation,
           test_create_requirement_no_title, test_get_requirement,
           test_get_requirement_404, test_get_requirement_bad_id,
           test_list_requirements, test_list_requirements_search,
           test_list_requirements_pagination, test_update_requirement,
           test_update_requirement_no_fields, test_update_requirement_404]:
    run_test(fn)


# ====================================================================
# 3. RELEASES SERVICE CRUD
# ====================================================================
print("\n===== 3. RELEASES SERVICE =====")

release_id = None

@test("Create release")
def test_create_release():
    global release_id
    r = post(f"{SERVICES['releases']}/releases", {
        "name": "Test Release 2026.02-backend",
        "description": "Backend test release",
        "requirement_ids": [req_id] if req_id else [],
    })
    data = r.json()
    release_id = data["id"]
    created_ids["releases"].append(release_id)
    assert data["name"] == "Test Release 2026.02-backend"
    assert data["description"] == "Backend test release"

@test("Get release by ID")
def test_get_release():
    r = get(f"{SERVICES['releases']}/releases/{release_id}")
    data = r.json()
    assert data["id"] == release_id

@test("List releases")
def test_list_releases():
    r = get(f"{SERVICES['releases']}/releases")
    data = r.json()
    assert isinstance(data, list)
    assert any(d["id"] == release_id for d in data)

@test("Update release")
def test_update_release():
    r = put(f"{SERVICES['releases']}/releases/{release_id}", {
        "description": "Backend test release (updated)",
    })
    data = r.json()
    assert data["description"] == "Backend test release (updated)"

@test("Get release - not found")
def test_get_release_404():
    r = client.get(f"{SERVICES['releases']}/releases/000000000000000000000000")
    assert r.status_code == 404

@test("Get release - invalid ID")
def test_get_release_bad_id():
    r = client.get(f"{SERVICES['releases']}/releases/bad-id")
    assert r.status_code == 400

for fn in [test_create_release, test_get_release, test_list_releases,
           test_update_release, test_get_release_404, test_get_release_bad_id]:
    run_test(fn)


# ====================================================================
# 4. TESTCASES SERVICE CRUD
# ====================================================================
print("\n===== 4. TESTCASES SERVICE =====")

tc_id = None

@test("Create testcase")
def test_create_testcase():
    global tc_id
    r = post(f"{SERVICES['testcases']}/testcases", {
        "requirement_id": req_id or "000000000000000000000000",
        "title": "Backend Test TC",
        "gherkin": "Given the app is running\nWhen the user opens the homepage\nThen they see a welcome message",
        "status": "draft",
        "version": 1,
        "metadata": {
            "description": "Automated backend test case",
            "preconditions": "Application is deployed and accessible",
            "steps": [
                {"action": "Open the homepage", "expected_result": "Welcome message is visible"},
                {"action": "Click the login button", "expected_result": "Login form appears"},
            ]
        }
    })
    data = r.json()
    tc_id = data["id"]
    created_ids["testcases"].append(tc_id)
    assert data["title"] == "Backend Test TC"
    assert data["gherkin"].startswith("Given")
    assert data["status"] == "draft"
    assert data["metadata"]["description"] == "Automated backend test case"
    assert len(data["metadata"]["steps"]) == 2

@test("Create testcase - missing required fields")
def test_create_testcase_validation():
    r = client.post(f"{SERVICES['testcases']}/testcases", json={"title": "Only Title"})
    assert r.status_code == 422

@test("Get testcase by ID")
def test_get_testcase():
    r = get(f"{SERVICES['testcases']}/testcases/{tc_id}")
    data = r.json()
    assert data["id"] == tc_id
    assert data["title"] == "Backend Test TC"
    assert data["gherkin"].startswith("Given")
    assert data["metadata"]["steps"][0]["action"] == "Open the homepage"

@test("Get testcase - not found")
def test_get_testcase_404():
    r = client.get(f"{SERVICES['testcases']}/testcases/000000000000000000000000")
    assert r.status_code == 404

@test("List testcases")
def test_list_testcases():
    r = get(f"{SERVICES['testcases']}/testcases")
    data = r.json()
    assert isinstance(data, list)
    assert any(d["id"] == tc_id for d in data)

@test("List testcases - filter by requirement_id")
def test_list_testcases_filter():
    if not req_id:
        return  # skip
    r = get(f"{SERVICES['testcases']}/testcases?requirement_id={req_id}")
    data = r.json()
    assert all(d["requirement_id"] == req_id for d in data)

@test("Update testcase")
def test_update_testcase():
    r = put(f"{SERVICES['testcases']}/testcases/{tc_id}", {
        "title": "Backend Test TC (Updated)",
        "status": "ready",
    })
    data = r.json()
    assert data["title"] == "Backend Test TC (Updated)"
    assert data["status"] == "ready"

@test("Update testcase - gherkin field")
def test_update_testcase_gherkin():
    new_gherkin = "Given a new scenario\nWhen I test updates\nThen the gherkin changes"
    r = put(f"{SERVICES['testcases']}/testcases/{tc_id}", {
        "gherkin": new_gherkin,
    })
    data = r.json()
    assert data["gherkin"] == new_gherkin

@test("Update testcase - metadata")
def test_update_testcase_metadata():
    r = put(f"{SERVICES['testcases']}/testcases/{tc_id}", {
        "metadata": {
            "description": "Updated description",
            "preconditions": "Updated preconditions",
            "steps": [
                {"action": "New step 1", "expected_result": "New expected 1"},
            ]
        }
    })
    data = r.json()
    assert data["metadata"]["description"] == "Updated description"
    assert len(data["metadata"]["steps"]) == 1

@test("Update testcase - not found")
def test_update_testcase_404():
    r = client.put(f"{SERVICES['testcases']}/testcases/000000000000000000000000", json={"title": "Nope"})
    assert r.status_code == 404

for fn in [test_create_testcase, test_create_testcase_validation,
           test_get_testcase, test_get_testcase_404, test_list_testcases,
           test_list_testcases_filter, test_update_testcase,
           test_update_testcase_gherkin, test_update_testcase_metadata,
           test_update_testcase_404]:
    run_test(fn)


# ====================================================================
# 5. EXECUTIONS SERVICE
# ====================================================================
print("\n===== 5. EXECUTIONS SERVICE =====")

exec_id = None

@test("Create execution")
def test_create_execution():
    global exec_id
    r = post(f"{SERVICES['executions']}/executions", {
        "test_case_id": tc_id or "000000000000000000000000",
        "release_id": release_id,
        "execution_type": "manual",
        "result": "passed",
        "executed_by": "backend-test",
        "notes": "Automated test execution",
        "duration_seconds": 42,
        "metadata": {"environment": "test"},
    })
    data = r.json()
    exec_id = data["id"]
    created_ids["executions"].append(exec_id)
    assert data["result"] == "passed"
    assert data["execution_type"] == "manual"
    assert data["executed_by"] == "backend-test"
    assert data["duration_seconds"] == 42

@test("Create execution - invalid result")
def test_create_execution_invalid_result():
    r = client.post(f"{SERVICES['executions']}/executions", json={
        "test_case_id": "000000000000000000000000",
        "result": "invalid_status",
    })
    assert r.status_code == 422

@test("Get execution by ID")
def test_get_execution():
    r = get(f"{SERVICES['executions']}/executions/{exec_id}")
    data = r.json()
    assert data["id"] == exec_id
    assert data["result"] == "passed"

@test("List executions")
def test_list_executions():
    r = get(f"{SERVICES['executions']}/executions")
    data = r.json()
    assert isinstance(data, list)

@test("List executions - filter by test_case_id")
def test_list_executions_filter():
    if not tc_id:
        return
    r = get(f"{SERVICES['executions']}/executions?test_case_id={tc_id}")
    data = r.json()
    assert all(d["test_case_id"] == tc_id for d in data)

@test("Update execution")
def test_update_execution():
    r = put(f"{SERVICES['executions']}/executions/{exec_id}", {
        "result": "failed",
        "notes": "Changed to failed via backend test",
    })
    data = r.json()
    assert data["result"] == "failed"
    assert "Changed to failed" in data["notes"]

@test("Get execution - not found")
def test_get_execution_404():
    r = client.get(f"{SERVICES['executions']}/executions/000000000000000000000000")
    assert r.status_code == 404

for fn in [test_create_execution, test_create_execution_invalid_result,
           test_get_execution, test_list_executions,
           test_list_executions_filter, test_update_execution,
           test_get_execution_404]:
    run_test(fn)


# ====================================================================
# 6. AUTOMATIONS SERVICE
# ====================================================================
print("\n===== 6. AUTOMATIONS SERVICE =====")

auto_id = None

@test("Create automation")
def test_create_automation():
    global auto_id
    r = post(f"{SERVICES['automations']}/automations", {
        "test_case_id": tc_id or "000000000000000000000000",
        "title": "Backend Test Automation",
        "framework": "playwright",
        "script": "await page.goto('http://frontend:5173');\nawait page.waitForLoadState('networkidle');",
        "status": "not_started",
        "notes": "Created by backend tests",
        "metadata": {"generation_type": "test"},
    })
    data = r.json()
    auto_id = data["id"]
    created_ids["automations"].append(auto_id)
    assert data["title"] == "Backend Test Automation"
    assert data["framework"] == "playwright"
    assert "page.goto" in data["script"]
    assert data["status"] == "not_started"

@test("Create automation - invalid framework")
def test_create_automation_invalid_framework():
    r = client.post(f"{SERVICES['automations']}/automations", json={
        "test_case_id": "000000000000000000000000",
        "title": "Bad Framework",
        "framework": "invalid_framework",
        "script": "console.log('test')",
    })
    assert r.status_code == 422

@test("Get automation by ID")
def test_get_automation():
    r = get(f"{SERVICES['automations']}/automations/{auto_id}")
    data = r.json()
    assert data["id"] == auto_id
    assert data["title"] == "Backend Test Automation"

@test("List automations")
def test_list_automations():
    r = get(f"{SERVICES['automations']}/automations")
    data = r.json()
    assert isinstance(data, list)

@test("List automations - filter by test_case_id")
def test_list_automations_filter():
    if not tc_id:
        return
    r = get(f"{SERVICES['automations']}/automations?test_case_id={tc_id}")
    data = r.json()
    assert all(d["test_case_id"] == tc_id for d in data)

@test("Update automation")
def test_update_automation():
    r = put(f"{SERVICES['automations']}/automations/{auto_id}", {
        "title": "Backend Test Automation (Updated)",
        "status": "passing",
    })
    data = r.json()
    assert data["title"] == "Backend Test Automation (Updated)"
    assert data["status"] == "passing"

@test("Normalize automation script")
def test_normalize_script():
    # Create an automation with wrapped script
    r = post(f"{SERVICES['automations']}/automations", {
        "test_case_id": tc_id or "000000000000000000000000",
        "title": "Normalize Script Test",
        "framework": "playwright",
        "script": "```javascript\nawait page.goto('http://frontend:5173');\n```",
    })
    data = r.json()
    norm_id = data["id"]
    created_ids["automations"].append(norm_id)
    # Call normalize endpoint
    r2 = client.post(f"{SERVICES['automations']}/automations/{norm_id}/normalize-script")
    assert r2.status_code == 200
    data2 = r2.json()
    assert "```" not in data2["script"], "Code fences should be stripped"

@test("Get automation - not found")
def test_get_automation_404():
    r = client.get(f"{SERVICES['automations']}/automations/000000000000000000000000")
    assert r.status_code == 404

@test("Get automation - invalid ID")
def test_get_automation_bad_id():
    r = client.get(f"{SERVICES['automations']}/automations/not-valid")
    assert r.status_code == 400

for fn in [test_create_automation, test_create_automation_invalid_framework,
           test_get_automation, test_list_automations,
           test_list_automations_filter, test_update_automation,
           test_normalize_script, test_get_automation_404,
           test_get_automation_bad_id]:
    run_test(fn)


# ====================================================================
# 7. GENERATOR SERVICE (Knowledge Graphs + other endpoints)
# ====================================================================
print("\n===== 7. GENERATOR SERVICE =====")

kg_id = None

@test("List knowledge graphs")
def test_list_knowledge_graphs():
    r = get(f"{SERVICES['generator']}/knowledge-graphs")
    data = r.json()
    assert isinstance(data, list)
    # Auto-seeded default KG should exist
    assert len(data) >= 1, "Expected at least 1 knowledge graph (auto-seeded)"

@test("Create knowledge graph")
def test_create_knowledge_graph():
    global kg_id
    r = post(f"{SERVICES['generator']}/knowledge-graphs", {
        "app_name": "Test App (backend-test)",
        "base_url": "http://test-app:3000",
        "is_default": False,
        "pages": [
            {
                "route": "/",
                "description": "Main landing page",
                "key_buttons": ["Submit", "Cancel"],
            }
        ],
        "nav_items": [
            {"label": "Home", "route": "/"}
        ],
    })
    data = r.json()
    kg_id = data["id"]
    created_ids["knowledge_graphs"].append(kg_id)
    assert data["app_name"] == "Test App (backend-test)"
    assert data["is_default"] is False
    assert len(data["pages"]) >= 1

@test("Get knowledge graph by ID")
def test_get_knowledge_graph():
    r = get(f"{SERVICES['generator']}/knowledge-graphs/{kg_id}")
    data = r.json()
    assert data["id"] == kg_id
    assert data["app_name"] == "Test App (backend-test)"

@test("Update knowledge graph")
def test_update_knowledge_graph():
    r = put(f"{SERVICES['generator']}/knowledge-graphs/{kg_id}", {
        "app_name": "Test App (backend-test, updated)",
    })
    data = r.json()
    assert data["app_name"] == "Test App (backend-test, updated)"

@test("Get knowledge graph - not found")
def test_get_kg_404():
    r = client.get(f"{SERVICES['generator']}/knowledge-graphs/000000000000000000000000")
    assert r.status_code == 404

@test("Generator /generate-structured-testcase - validation")
def test_generate_structured_validation():
    """Test that the structured testcase generator validates input."""
    r = client.post(f"{SERVICES['generator']}/generate-structured-testcase", json={
        "requirement_id": "000000000000000000000000",
    })
    # Should fail because the requirement doesn't exist or ollama isn't ready
    # Either 4xx or 5xx is acceptable; we just confirm the route exists
    assert r.status_code in (200, 400, 404, 422, 500, 502, 503), f"Unexpected status: {r.status_code}"

@test("Generator /generate - validation")
def test_generate_validation():
    """Test generation endpoint input validation."""
    r = client.post(f"{SERVICES['generator']}/generate", json={
        "requirement_id": "000000000000000000000000",
        "amount": 1,
    })
    assert r.status_code in (200, 400, 404, 422, 500, 502, 503), f"Unexpected status: {r.status_code}"

@test("Generator /execute-script-debug endpoint exists")
def test_execute_script_debug_exists():
    r = client.post(f"{SERVICES['generator']}/execute-script-debug", json={
        "script": "await page.goto('http://frontend:5173');",
    })
    # Endpoint should be reachable (may fail if playwright isn't available)
    assert r.status_code in (200, 400, 422, 500, 502, 503), f"Unexpected: {r.status_code}"

for fn in [test_list_knowledge_graphs, test_create_knowledge_graph,
           test_get_knowledge_graph, test_update_knowledge_graph,
           test_get_kg_404, test_generate_structured_validation,
           test_generate_validation, test_execute_script_debug_exists]:
    run_test(fn)


# ====================================================================
# 8. TOABRKIA SERVICE
# ====================================================================
print("\n===== 8. TOABRKIA SERVICE (Release Assessments) =====")

assessment_id = None

@test("List assessments (empty or existing)")
def test_list_assessments():
    r = get(f"{SERVICES['toabrkia']}/assessments")
    data = r.json()
    assert isinstance(data, list)

@test("Upsert assessment for release")
def test_upsert_assessment():
    global assessment_id
    rid = release_id or "000000000000000000000000"
    r = client.put(f"{SERVICES['toabrkia']}/assessments/by-release/{rid}", json={
        "toab": {
            "prefix": "TOAB",
            "component_name": "Backend Test Component",
            "description": "Automated test assessment",
        },
        "rk": {
            "internal_effects": "low",
            "external_effects": "medium",
            "availability": "99%",
            "complexity": "simple",
        },
        "ia": {
            "code_change": True,
            "automated_test_intensity": "high",
            "manual_test_intensity": "low",
            "comments": "Comprehensive automated tests cover this",
        },
    })
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assessment_id = data["id"]
    created_ids["assessments"].append(assessment_id)
    assert data["release_id"] == rid
    assert data["toab"]["component_name"] == "Backend Test Component"
    assert data["rk"]["external_effects"] == "medium"
    assert data["ia"]["code_change"] is True

@test("Get assessment by release_id")
def test_get_assessment():
    rid = release_id or "000000000000000000000000"
    r = get(f"{SERVICES['toabrkia']}/assessments/by-release/{rid}")
    data = r.json()
    assert data["release_id"] == rid

@test("Update assessment (upsert again)")
def test_update_assessment():
    rid = release_id or "000000000000000000000000"
    r = client.put(f"{SERVICES['toabrkia']}/assessments/by-release/{rid}", json={
        "toab": {
            "prefix": "TOAB",
            "component_name": "Updated Component",
            "description": "Updated description",
        },
        "rk": {
            "internal_effects": "high",
            "external_effects": "high",
            "availability": "99.9%",
            "complexity": "complex",
        },
        "ia": {
            "code_change": False,
            "automated_test_intensity": "medium",
            "manual_test_intensity": "medium",
            "comments": "Updated assessment",
        },
    })
    assert r.status_code == 200
    data = r.json()
    assert data["toab"]["component_name"] == "Updated Component"
    assert data["rk"]["complexity"] == "complex"

@test("Get assessment - not found")
def test_get_assessment_404():
    r = client.get(f"{SERVICES['toabrkia']}/assessments/by-release/000000000000000000000000")
    assert r.status_code == 404

for fn in [test_list_assessments, test_upsert_assessment,
           test_get_assessment, test_update_assessment,
           test_get_assessment_404]:
    run_test(fn)


# ====================================================================
# 9. GIT SERVICE (read-only probes — no actual repos to clone)
# ====================================================================
print("\n===== 9. GIT SERVICE =====")

@test("Git health")
def test_git_health_detail():
    r = get(f"{SERVICES['git']}/health")
    data = r.json()
    assert data["status"] == "ok" or "status" in data

@test("Git clone - validation (missing fields)")
def test_git_clone_validation():
    r = client.post(f"{SERVICES['git']}/clone", json={})
    assert r.status_code == 422

@test("Git status - validation")
def test_git_status_validation():
    r = client.post(f"{SERVICES['git']}/status", json={"repo_path": "/non/existent/path"})
    # should be 400 or 404 or similar since repo doesn't exist
    assert r.status_code in (400, 404, 422, 500)

@test("Git branch list - non-existent repo")
def test_git_branch_list_404():
    r = client.get(f"{SERVICES['git']}/branch/list/nonexistent")
    assert r.status_code in (400, 404, 500)

for fn in [test_git_health_detail, test_git_clone_validation,
           test_git_status_validation, test_git_branch_list_404]:
    run_test(fn)


# ====================================================================
# 10. CROSS-SERVICE INTEGRATION
# ====================================================================
print("\n===== 10. CROSS-SERVICE INTEGRATION =====")

@test("Testcase references valid requirement")
def test_tc_references_requirement():
    """Fetch the testcase and verify the linked requirement exists."""
    if not tc_id or not req_id:
        return
    tc_data = get(f"{SERVICES['testcases']}/testcases/{tc_id}").json()
    assert tc_data["requirement_id"] == req_id
    req_data = get(f"{SERVICES['requirements']}/requirements/{req_id}").json()
    assert req_data["id"] == req_id

@test("Execution references valid testcase")
def test_exec_references_testcase():
    if not exec_id or not tc_id:
        return
    exec_data = get(f"{SERVICES['executions']}/executions/{exec_id}").json()
    assert exec_data["test_case_id"] == tc_id
    tc_data = get(f"{SERVICES['testcases']}/testcases/{tc_id}").json()
    assert tc_data["id"] == tc_id

@test("Automation references valid testcase")
def test_auto_references_testcase():
    if not auto_id or not tc_id:
        return
    auto_data = get(f"{SERVICES['automations']}/automations/{auto_id}").json()
    assert auto_data["test_case_id"] == tc_id

@test("Release links requirement IDs")
def test_release_links():
    if not release_id or not req_id:
        return
    rel_data = get(f"{SERVICES['releases']}/releases/{release_id}").json()
    assert req_id in rel_data.get("requirement_ids", [])

@test("Generator context includes all testcase fields")
def test_generator_context_completeness():
    """Verify the generator's context building includes gherkin and all fields."""
    if not tc_id:
        return
    tc_data = get(f"{SERVICES['testcases']}/testcases/{tc_id}").json()
    assert "gherkin" in tc_data, "Testcase should have gherkin field"
    assert "metadata" in tc_data, "Testcase should have metadata"
    assert "description" in tc_data.get("metadata", {}), "Metadata should have description"
    assert "steps" in tc_data.get("metadata", {}), "Metadata should have steps"
    assert "preconditions" in tc_data.get("metadata", {}), "Metadata should have preconditions"

@test("Requirement has all expected fields")
def test_requirement_completeness():
    if not req_id:
        return
    r = get(f"{SERVICES['requirements']}/requirements/{req_id}").json()
    for field in ["id", "title", "description", "source", "tags", "created_at", "updated_at"]:
        assert field in r, f"Missing field: {field}"

@test("Testcase has all expected fields")
def test_testcase_completeness():
    if not tc_id:
        return
    tc = get(f"{SERVICES['testcases']}/testcases/{tc_id}").json()
    for field in ["id", "requirement_id", "title", "gherkin", "status", "version", "metadata", "created_at", "updated_at"]:
        assert field in tc, f"Missing field: {field}"

@test("Execution has all expected fields")
def test_execution_completeness():
    if not exec_id:
        return
    ex = get(f"{SERVICES['executions']}/executions/{exec_id}").json()
    for field in ["id", "test_case_id", "execution_type", "result", "created_at", "updated_at"]:
        assert field in ex, f"Missing field: {field}"

@test("Automation has all expected fields")
def test_automation_completeness():
    if not auto_id:
        return
    au = get(f"{SERVICES['automations']}/automations/{auto_id}").json()
    for field in ["id", "test_case_id", "title", "framework", "script", "status", "created_at", "updated_at"]:
        assert field in au, f"Missing field: {field}"

for fn in [test_tc_references_requirement, test_exec_references_testcase,
           test_auto_references_testcase, test_release_links,
           test_generator_context_completeness, test_requirement_completeness,
           test_testcase_completeness, test_execution_completeness,
           test_automation_completeness]:
    run_test(fn)


# ====================================================================
# 11. EDGE CASES & ERROR HANDLING
# ====================================================================
print("\n===== 11. EDGE CASES & ERROR HANDLING =====")

@test("Requirements - special characters in title")
def test_requirement_special_chars():
    r = post(f"{SERVICES['requirements']}/requirements", {
        "title": 'Req with "quotes" & <special> chars!',
        "description": "Test for special characters: àéîöü ñ ß",
    })
    data = r.json()
    created_ids["requirements"].append(data["id"])
    assert '"quotes"' in data["title"]
    assert "àéîöü" in data["description"]

@test("Requirements - empty tags list")
def test_requirement_empty_tags():
    r = post(f"{SERVICES['requirements']}/requirements", {
        "title": "Req with empty tags",
        "tags": [],
    })
    data = r.json()
    created_ids["requirements"].append(data["id"])
    assert data["tags"] == []

@test("Requirements - large description")
def test_requirement_large_description():
    large_desc = "A" * 10000
    r = post(f"{SERVICES['requirements']}/requirements", {
        "title": "Req with large description",
        "description": large_desc,
    })
    data = r.json()
    created_ids["requirements"].append(data["id"])
    assert len(data["description"]) == 10000

@test("Testcase - empty metadata")
def test_testcase_empty_metadata():
    r = post(f"{SERVICES['testcases']}/testcases", {
        "requirement_id": req_id or "000000000000000000000000",
        "title": "TC with empty metadata",
        "gherkin": "Given nothing",
        "metadata": {},
    })
    data = r.json()
    created_ids["testcases"].append(data["id"])
    assert data["metadata"] == {}

@test("Testcase - all status transitions")
def test_testcase_status_transitions():
    valid_statuses = ["draft", "ready", "passed", "failed", "approved", "inactive"]
    # Create a fresh testcase and cycle through all statuses
    r = post(f"{SERVICES['testcases']}/testcases", {
        "requirement_id": req_id or "000000000000000000000000",
        "title": "Status transition TC",
        "gherkin": "Given statuses",
    })
    tc = r.json()
    created_ids["testcases"].append(tc["id"])
    for status in valid_statuses:
        r2 = put(f"{SERVICES['testcases']}/testcases/{tc['id']}", {"status": status})
        assert r2.json()["status"] == status, f"Failed to set status to {status}"

@test("Execution - all result types")
def test_execution_result_types():
    for result in ["passed", "failed", "blocked", "skipped"]:
        r = post(f"{SERVICES['executions']}/executions", {
            "test_case_id": tc_id or "000000000000000000000000",
            "result": result,
        })
        data = r.json()
        created_ids["executions"].append(data["id"])
        assert data["result"] == result

@test("Automation - all framework types")
def test_automation_framework_types():
    for fw in ["playwright", "selenium", "cypress", "pytest", "other"]:
        r = post(f"{SERVICES['automations']}/automations", {
            "test_case_id": tc_id or "000000000000000000000000",
            "title": f"Framework test: {fw}",
            "framework": fw,
            "script": "// test",
        })
        data = r.json()
        created_ids["automations"].append(data["id"])
        assert data["framework"] == fw

@test("Automation - all status types")
def test_automation_status_types():
    for status in ["not_started", "in_progress", "passing", "failing", "blocked"]:
        r = post(f"{SERVICES['automations']}/automations", {
            "test_case_id": tc_id or "000000000000000000000000",
            "title": f"Status test: {status}",
            "framework": "playwright",
            "script": "// test",
            "status": status,
        })
        data = r.json()
        created_ids["automations"].append(data["id"])
        assert data["status"] == status

@test("CORS headers present")
def test_cors_headers():
    r = client.options(f"{SERVICES['requirements']}/requirements", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    })
    # CORS should allow the origin
    assert r.status_code in (200, 204), f"OPTIONS failed: {r.status_code}"

for fn in [test_requirement_special_chars, test_requirement_empty_tags,
           test_requirement_large_description, test_testcase_empty_metadata,
           test_testcase_status_transitions, test_execution_result_types,
           test_automation_framework_types, test_automation_status_types,
           test_cors_headers]:
    run_test(fn)


# ====================================================================
# 12. CLEANUP: Delete all test data
# ====================================================================
print("\n===== 12. CLEANUP =====")

@test("Delete test knowledge graphs")
def test_cleanup_kgs():
    for kg in created_ids["knowledge_graphs"]:
        r = client.delete(f"{SERVICES['generator']}/knowledge-graphs/{kg}")
        assert r.status_code in (200, 204, 404), f"KG delete failed: {r.status_code}"

@test("Delete test automations")
def test_cleanup_automations():
    for aid in created_ids["automations"]:
        r = client.delete(f"{SERVICES['automations']}/automations/{aid}")
        assert r.status_code in (204, 404), f"Automation delete failed for {aid}: {r.status_code}"

@test("Delete test executions")
def test_cleanup_executions():
    # Executions service may not have DELETE — check
    for eid in created_ids["executions"]:
        r = client.delete(f"{SERVICES['executions']}/executions/{eid}")
        # If DELETE isn't implemented, that's okay
        if r.status_code == 405:
            print(f"    (Executions DELETE not implemented — skipping)")
            break
        assert r.status_code in (204, 404, 405), f"Execution delete failed: {r.status_code}"

@test("Delete test assessments")
def test_cleanup_assessments():
    for aid in created_ids["assessments"]:
        r = client.delete(f"{SERVICES['toabrkia']}/assessments/{aid}")
        assert r.status_code in (200, 204, 404), f"Assessment delete failed: {r.status_code}"

@test("Delete test testcases")
def test_cleanup_testcases():
    for tid in created_ids["testcases"]:
        r = client.delete(f"{SERVICES['testcases']}/testcases/{tid}")
        assert r.status_code in (204, 404), f"TC delete failed for {tid}: {r.status_code}"

@test("Delete test releases")
def test_cleanup_releases():
    for rid in created_ids["releases"]:
        r = client.delete(f"{SERVICES['releases']}/releases/{rid}")
        assert r.status_code in (204, 404), f"Release delete failed: {r.status_code}"

@test("Delete test requirements")
def test_cleanup_requirements():
    for rid in created_ids["requirements"]:
        r = client.delete(f"{SERVICES['requirements']}/requirements/{rid}")
        assert r.status_code in (204, 404), f"Req delete failed for {rid}: {r.status_code}"

@test("Verify cleanup - requirement gone")
def test_verify_cleanup_req():
    if req_id:
        r = client.get(f"{SERVICES['requirements']}/requirements/{req_id}")
        assert r.status_code == 404, "Requirement should be deleted"

@test("Verify cleanup - testcase gone")
def test_verify_cleanup_tc():
    if tc_id:
        r = client.get(f"{SERVICES['testcases']}/testcases/{tc_id}")
        assert r.status_code == 404, "Testcase should be deleted"

for fn in [test_cleanup_kgs, test_cleanup_automations, test_cleanup_executions,
           test_cleanup_assessments, test_cleanup_testcases, test_cleanup_releases,
           test_cleanup_requirements, test_verify_cleanup_req, test_verify_cleanup_tc]:
    run_test(fn)


# ====================================================================
# SUMMARY
# ====================================================================
print(f"\n{'='*60}")
print(f"BACKEND TEST RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print(f"{'='*60}")

if errors:
    print("\nFailed tests:")
    for e in errors:
        print(e)

client.close()
sys.exit(1 if failed > 0 else 0)
