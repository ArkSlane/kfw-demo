"""LLM connection storage for Git service.

Stores connection metadata + API keys (as secrets) in the git service volume.
API keys are never returned by the API.

This is file-backed secret storage (not encryption) and relies on container/volume access control.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional
from uuid import uuid4

from fastapi import HTTPException

LLMProvider = Literal["openai", "azure", "aws", "google", "other"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_secret(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 8:
        return "********"
    return f"{v[:4]}…{v[-4:]}"


@dataclass(frozen=True)
class StoredLLMConnection:
    id: str
    provider: LLMProvider
    name: str
    base_url: str
    default_model: Optional[str]
    created_at: str
    api_key_masked: str


class LLMConnectionsStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.base_dir, 0o700)
        except Exception:
            pass

    def _path(self, connection_id: str) -> Path:
        return self.base_dir / f"{connection_id}.json"

    def list(self) -> list[StoredLLMConnection]:
        items: list[StoredLLMConnection] = []
        for file in self.base_dir.glob("*.json"):
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
                api_key = str(raw.get("api_key", ""))
                items.append(
                    StoredLLMConnection(
                        id=str(raw.get("id") or file.stem),
                        provider=raw.get("provider"),
                        name=str(raw.get("name", "")).strip(),
                        base_url=str(raw.get("base_url", "")).strip(),
                        default_model=(raw.get("default_model") or None),
                        created_at=str(raw.get("created_at", "")) or "",
                        api_key_masked=_mask_secret(api_key),
                    )
                )
            except Exception:
                continue

        items.sort(key=lambda c: c.created_at or "", reverse=True)
        return items

    def create(self, *, provider: LLMProvider, name: str, base_url: str, api_key: str, default_model: Optional[str] = None) -> StoredLLMConnection:
        name = (name or "").strip()
        base_url = (base_url or "").strip()
        api_key = (api_key or "").strip()
        default_model = (default_model or "").strip() or None

        if not name:
            raise HTTPException(status_code=400, detail="Connection name is required")
        if not base_url:
            raise HTTPException(status_code=400, detail="Base URL is required")
        if not api_key:
            raise HTTPException(status_code=400, detail="API key is required")

        connection_id = uuid4().hex
        created_at = now_iso()

        payload = {
            "id": connection_id,
            "provider": provider,
            "name": name,
            "base_url": base_url,
            "default_model": default_model,
            "api_key": api_key,
            "created_at": created_at,
        }

        path = self._path(connection_id)
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except Exception as e:
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=f"Failed to store LLM connection: {str(e)}")

        return StoredLLMConnection(
            id=connection_id,
            provider=provider,
            name=name,
            base_url=base_url,
            default_model=default_model,
            created_at=created_at,
            api_key_masked=_mask_secret(api_key),
        )

    def delete(self, connection_id: str) -> None:
        path = self._path(connection_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="LLM connection not found")
        try:
            path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete LLM connection: {str(e)}")
