"""
Shared health check utilities for all services.
Provides dependency health checks for MongoDB, Azure OpenAI LLM, and Playwright MCP.
"""
import httpx
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient


async def check_mongodb(mongo_url: str, db_name: str) -> dict:
    """
    Check MongoDB connection health.
    
    Returns:
        dict with status, message, and response_time_ms
    """
    start_time = datetime.now(timezone.utc)
    
    try:
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=2000)
        # Ping the database to verify connection
        await client[db_name].command('ping')
        
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "status": "healthy",
            "message": "MongoDB connection successful",
            "response_time_ms": round(response_time_ms, 2),
            "database": db_name
        }
    except Exception as e:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "status": "unhealthy",
            "message": f"MongoDB connection failed: {str(e)}",
            "response_time_ms": round(response_time_ms, 2),
            "database": db_name
        }
    finally:
        try:
            client.close()
        except:
            pass


async def check_azure_llm(endpoint: str, api_key: str, timeout: float = 5.0) -> dict:
    """
    Check Azure OpenAI (AI Foundry) service health.
    
    Returns:
        dict with status, message, and response_time_ms
    """
    start_time = datetime.now(timezone.utc)

    if not endpoint or not api_key:
        return {
            "status": "unhealthy",
            "message": "Azure OpenAI endpoint or API key not configured",
            "response_time_ms": 0,
        }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Call the deployments list endpoint to verify connectivity
            url = f"{endpoint.rstrip('/')}/openai/models?api-version=2024-12-01-preview"
            response = await client.get(url, headers={"api-key": api_key})
            response.raise_for_status()

            response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return {
                "status": "healthy",
                "message": "Azure OpenAI service available",
                "response_time_ms": round(response_time_ms, 2),
                "endpoint": endpoint,
            }
    except httpx.TimeoutException:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        return {
            "status": "unhealthy",
            "message": "Azure OpenAI service timeout",
            "response_time_ms": round(response_time_ms, 2),
            "endpoint": endpoint,
        }
    except Exception as e:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        return {
            "status": "unhealthy",
            "message": f"Azure OpenAI service error: {str(e)}",
            "response_time_ms": round(response_time_ms, 2),
            "endpoint": endpoint,
        }


async def check_playwright_mcp(mcp_url: str, timeout: float = 2.0) -> dict:
    """
    Check Playwright MCP service health.
    
    Returns:
        dict with status, message, and response_time_ms
    """
    start_time = datetime.now(timezone.utc)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{mcp_url}/health")
            response.raise_for_status()
            
            response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "message": "Playwright MCP service available",
                "response_time_ms": round(response_time_ms, 2),
                "url": mcp_url
            }
    except httpx.TimeoutException:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "status": "unhealthy",
            "message": "Playwright MCP service timeout",
            "response_time_ms": round(response_time_ms, 2),
            "url": mcp_url
        }
    except Exception as e:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "status": "unhealthy",
            "message": f"Playwright MCP service error: {str(e)}",
            "response_time_ms": round(response_time_ms, 2),
            "url": mcp_url
        }


async def check_http_service(service_name: str, service_url: str, endpoint: str = "/health", timeout: float = 2.0) -> dict:
    """
    Generic HTTP service health check.
    
    Returns:
        dict with status, message, and response_time_ms
    """
    start_time = datetime.now(timezone.utc)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{service_url}{endpoint}")
            response.raise_for_status()
            
            response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "message": f"{service_name} service available",
                "response_time_ms": round(response_time_ms, 2),
                "url": service_url
            }
    except httpx.TimeoutException:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "status": "unhealthy",
            "message": f"{service_name} service timeout",
            "response_time_ms": round(response_time_ms, 2),
            "url": service_url
        }
    except Exception as e:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "status": "unhealthy",
            "message": f"{service_name} service error: {str(e)}",
            "response_time_ms": round(response_time_ms, 2),
            "url": service_url
        }


def aggregate_health_status(dependencies: dict) -> str:
    """
    Aggregate health status from multiple dependencies.
    
    Returns:
        "healthy" if all dependencies are healthy, otherwise "degraded" or "unhealthy"
    """
    statuses = [dep.get("status", "unknown") for dep in dependencies.values()]
    
    if all(status == "healthy" for status in statuses):
        return "healthy"
    elif any(status == "unhealthy" for status in statuses):
        return "degraded"
    else:
        return "unknown"
