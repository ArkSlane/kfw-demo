"""
Shared health check utilities for all services.
Provides dependency health checks for MongoDB, Ollama, and Playwright MCP.
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


async def check_ollama(ollama_url: str, timeout: float = 2.0) -> dict:
    """
    Check Ollama service health.
    
    Returns:
        dict with status, message, and response_time_ms
    """
    start_time = datetime.now(timezone.utc)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            response.raise_for_status()
            
            response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            models = response.json().get('models', [])
            model_count = len(models)

            required_model = None
            try:
                import os
                required_model = (os.getenv("OLLAMA_MODEL") or "").strip() or None
            except Exception:
                required_model = None

            model_names = [m.get("name") for m in models if isinstance(m, dict)]

            # If Ollama is reachable but not usable for generation, report degraded.
            if model_count == 0:
                return {
                    "status": "degraded",
                    "message": "Ollama reachable but no models are installed (generation will fail)",
                    "response_time_ms": round(response_time_ms, 2),
                    "url": ollama_url,
                    "models_available": model_count,
                    "required_model": required_model,
                }

            if required_model and required_model not in model_names:
                return {
                    "status": "degraded",
                    "message": f"Ollama reachable but required model '{required_model}' is not installed",
                    "response_time_ms": round(response_time_ms, 2),
                    "url": ollama_url,
                    "models_available": model_count,
                    "required_model": required_model,
                }
            
            return {
                "status": "healthy",
                "message": f"Ollama service available with {model_count} model(s)",
                "response_time_ms": round(response_time_ms, 2),
                "url": ollama_url,
                "models_available": model_count
            }
    except httpx.TimeoutException:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "status": "unhealthy",
            "message": "Ollama service timeout",
            "response_time_ms": round(response_time_ms, 2),
            "url": ollama_url
        }
    except Exception as e:
        response_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "status": "unhealthy",
            "message": f"Ollama service error: {str(e)}",
            "response_time_ms": round(response_time_ms, 2),
            "url": ollama_url
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
