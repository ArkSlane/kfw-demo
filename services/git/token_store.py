"""API Token Storage for Git Service.

Stores provider API tokens (GitHub/GitLab/Azure DevOps) on disk in a Docker volume,
with restrictive file permissions. Tokens are never returned by the API.

Note: This is not encryption; it relies on container/volume access control.
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

Provider = Literal["github", "gitlab", "azureDevOps"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_token(token: str) -> str:
    t = (token or "").strip()
    if not t:
        return ""
    if len(t) <= 8:
        return "********"
    return f"{t[:4]}…{t[-4:]}"


@dataclass(frozen=True)
class StoredToken:
    id: str
    provider: Provider
    name: str
    created_at: str
    token_masked: str
    azure_org: Optional[str] = None


class APITokenStore:
    """File-backed API token store."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.base_dir, 0o700)
        except Exception:
            # Best-effort (some FS/mounts may not support chmod semantics).
            pass

    def _token_path(self, token_id: str) -> Path:
        return self.base_dir / f"{token_id}.json"

    def list(self) -> list[StoredToken]:
        tokens: list[StoredToken] = []
        for file in self.base_dir.glob("*.json"):
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
                token_value = str(raw.get("token", ""))
                tokens.append(
                    StoredToken(
                        id=str(raw.get("id") or file.stem),
                        provider=raw.get("provider"),
                        name=str(raw.get("name", "")).strip(),
                        created_at=str(raw.get("created_at", "")) or "",
                        token_masked=_mask_token(token_value),
                        azure_org=(raw.get("azure_org") or None),
                    )
                )
            except Exception:
                # Skip malformed entries.
                continue

        # Newest first
        tokens.sort(key=lambda t: t.created_at or "", reverse=True)
        return tokens

    def create(self, *, provider: Provider, name: str, token: str, azure_org: Optional[str] = None) -> StoredToken:
        name = (name or "").strip()
        token = (token or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Token name is required")
        if not token:
            raise HTTPException(status_code=400, detail="Token value is required")

        token_id = uuid4().hex
        created_at = now_iso()

        payload = {
            "id": token_id,
            "provider": provider,
            "name": name,
            "token": token,
            "created_at": created_at,
            "azure_org": azure_org,
        }

        path = self._token_path(token_id)
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except Exception as e:
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=f"Failed to store token: {str(e)}")

        return StoredToken(
            id=token_id,
            provider=provider,
            name=name,
            created_at=created_at,
            token_masked=_mask_token(token),
            azure_org=azure_org,
        )

    def delete(self, token_id: str) -> None:
        path = self._token_path(token_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Token not found")
        try:
            path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete token: {str(e)}")

    def get_raw(self, token_id: str) -> dict:
        path = self._token_path(token_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Token not found")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read token: {str(e)}")

    def get_token_value(self, token_id: str) -> str:
        raw = self.get_raw(token_id)
        token_value = str(raw.get("token", "")).strip()
        if not token_value:
            raise HTTPException(status_code=500, detail="Stored token is empty")
        return token_value
