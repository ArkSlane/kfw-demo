"""Repo connection persistence for Git service.

Stores connected repo metadata (repo_url, local repo_path, auth reference) in the git
service volume. This is intentionally metadata-only; secrets stay in `token_store`.
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

Provider = Literal["github", "gitlab", "azureDevOps", "unknown"]
AuthType = Literal["api-token", "ssh-key", "none"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RepoConnection:
    id: str
    repo_url: str
    provider: Provider
    repo_path: str
    created_at: str
    last_synced_at: Optional[str]
    status: str
    auth_type: AuthType
    api_token_id: Optional[str] = None
    ssh_key_name: Optional[str] = None
    branch: Optional[str] = None


class RepoConnectionsStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.base_dir, 0o700)
        except Exception:
            pass

    def _path(self, connection_id: str) -> Path:
        return self.base_dir / f"{connection_id}.json"

    def list(self) -> list[RepoConnection]:
        items: list[RepoConnection] = []
        for file in self.base_dir.glob("*.json"):
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
                items.append(
                    RepoConnection(
                        id=str(raw.get("id") or file.stem),
                        repo_url=str(raw.get("repo_url", "")),
                        provider=raw.get("provider", "unknown"),
                        repo_path=str(raw.get("repo_path", "")),
                        created_at=str(raw.get("created_at", "")),
                        last_synced_at=raw.get("last_synced_at") or None,
                        status=str(raw.get("status", "connected")),
                        auth_type=raw.get("auth_type", "none"),
                        api_token_id=raw.get("api_token_id") or None,
                        ssh_key_name=raw.get("ssh_key_name") or None,
                        branch=raw.get("branch") or None,
                    )
                )
            except Exception:
                continue

        items.sort(key=lambda r: r.created_at or "", reverse=True)
        return items

    def get(self, connection_id: str) -> RepoConnection:
        path = self._path(connection_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Repo connection not found")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return RepoConnection(
                id=str(raw.get("id") or connection_id),
                repo_url=str(raw.get("repo_url", "")),
                provider=raw.get("provider", "unknown"),
                repo_path=str(raw.get("repo_path", "")),
                created_at=str(raw.get("created_at", "")),
                last_synced_at=raw.get("last_synced_at") or None,
                status=str(raw.get("status", "connected")),
                auth_type=raw.get("auth_type", "none"),
                api_token_id=raw.get("api_token_id") or None,
                ssh_key_name=raw.get("ssh_key_name") or None,
                branch=raw.get("branch") or None,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read repo connection: {str(e)}")

    def create(
        self,
        *,
        repo_url: str,
        provider: Provider,
        repo_path: str,
        auth_type: AuthType,
        api_token_id: Optional[str] = None,
        ssh_key_name: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> RepoConnection:
        connection_id = uuid4().hex
        created_at = now_iso()

        payload = {
            "id": connection_id,
            "repo_url": repo_url,
            "provider": provider,
            "repo_path": repo_path,
            "created_at": created_at,
            "last_synced_at": None,
            "status": "connected",
            "auth_type": auth_type,
            "api_token_id": api_token_id,
            "ssh_key_name": ssh_key_name,
            "branch": branch,
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
            raise HTTPException(status_code=500, detail=f"Failed to store repo connection: {str(e)}")

        return RepoConnection(
            id=connection_id,
            repo_url=repo_url,
            provider=provider,
            repo_path=repo_path,
            created_at=created_at,
            last_synced_at=None,
            status="connected",
            auth_type=auth_type,
            api_token_id=api_token_id,
            ssh_key_name=ssh_key_name,
            branch=branch,
        )

    def update(self, connection: RepoConnection) -> RepoConnection:
        path = self._path(connection.id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Repo connection not found")

        payload = {
            "id": connection.id,
            "repo_url": connection.repo_url,
            "provider": connection.provider,
            "repo_path": connection.repo_path,
            "created_at": connection.created_at,
            "last_synced_at": connection.last_synced_at,
            "status": connection.status,
            "auth_type": connection.auth_type,
            "api_token_id": connection.api_token_id,
            "ssh_key_name": connection.ssh_key_name,
            "branch": connection.branch,
        }

        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
            return connection
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update repo connection: {str(e)}")

    def delete(self, connection_id: str) -> None:
        path = self._path(connection_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Repo connection not found")
        try:
            path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete repo connection: {str(e)}")
