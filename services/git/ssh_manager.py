"""
SSH Key Management for Git Service

Provides secure storage and management of SSH keys for Git operations.
"""

import os
import stat
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
import subprocess


class SSHKeyManager:
    """Manages SSH keys for Git operations."""
    
    def __init__(self, keys_dir: Path):
        """
        Initialize SSH key manager.
        
        Args:
            keys_dir: Directory where SSH keys are stored
        """
        self.keys_dir = keys_dir
        self.keys_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        # SSH config file
        self.ssh_config_path = self.keys_dir / "config"
        
        # Known hosts file
        self.known_hosts_path = self.keys_dir / "known_hosts"
    
    def add_key(self, key_name: str, private_key: str, public_key: Optional[str] = None) -> dict:
        """
        Add an SSH key pair.
        
        Args:
            key_name: Name identifier for the key (e.g., "github_deploy")
            private_key: Private key content (PEM format)
            public_key: Optional public key content
        
        Returns:
            Dict with key information
        
        Raises:
            HTTPException: If key validation or storage fails
        """
        # Validate key name (alphanumeric, underscore, hyphen only)
        if not key_name.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(
                status_code=400,
                detail="Key name must contain only alphanumeric characters, underscores, and hyphens"
            )
        
        # Validate private key format
        if not private_key.strip().startswith("-----BEGIN"):
            raise HTTPException(
                status_code=400,
                detail="Invalid private key format. Must be PEM format starting with -----BEGIN"
            )
        
        private_key_path = self.keys_dir / f"{key_name}"
        public_key_path = self.keys_dir / f"{key_name}.pub"
        
        # Check if key already exists
        if private_key_path.exists():
            raise HTTPException(
                status_code=409,
                detail=f"SSH key '{key_name}' already exists"
            )
        
        try:
            # Write private key with secure permissions
            private_key_path.write_text(private_key.strip() + "\n")
            os.chmod(private_key_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            
            # Write public key if provided
            if public_key:
                public_key_path.write_text(public_key.strip() + "\n")
                os.chmod(public_key_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)  # 0o644
            
            # Validate key using ssh-keygen
            result = subprocess.run(
                ["ssh-keygen", "-l", "-f", str(private_key_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                # Clean up invalid key
                private_key_path.unlink()
                if public_key and public_key_path.exists():
                    public_key_path.unlink()
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid SSH key: {result.stderr}"
                )
            
            # Extract key fingerprint from ssh-keygen output
            fingerprint = result.stdout.strip()
            
            return {
                "key_name": key_name,
                "fingerprint": fingerprint,
                "has_public_key": public_key is not None,
                "path": str(private_key_path)
            }
        
        except HTTPException:
            raise
        except Exception as e:
            # Clean up on error
            if private_key_path.exists():
                private_key_path.unlink()
            if public_key and public_key_path.exists():
                public_key_path.unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store SSH key: {str(e)}"
            )
    
    def list_keys(self) -> list[dict]:
        """
        List all stored SSH keys.
        
        Returns:
            List of key information dicts
        """
        keys = []
        
        for key_file in self.keys_dir.glob("*"):
            # Skip non-key files
            if key_file.suffix in [".pub", ".config"] or key_file.name in ["config", "known_hosts"]:
                continue
            
            if key_file.is_file():
                # Get key fingerprint
                try:
                    result = subprocess.run(
                        ["ssh-keygen", "-l", "-f", str(key_file)],
                        capture_output=True,
                        text=True
                    )
                    
                    fingerprint = result.stdout.strip() if result.returncode == 0 else "Unknown"
                    
                    # Check for public key
                    pub_key_path = key_file.with_suffix(".pub")
                    has_public_key = pub_key_path.exists()
                    
                    keys.append({
                        "key_name": key_file.name,
                        "fingerprint": fingerprint,
                        "has_public_key": has_public_key,
                        "path": str(key_file)
                    })
                except Exception:
                    # Skip invalid keys
                    continue
        
        return keys
    
    def get_key(self, key_name: str) -> dict:
        """
        Get information about a specific SSH key.
        
        Args:
            key_name: Name of the key
        
        Returns:
            Key information dict
        
        Raises:
            HTTPException: If key not found
        """
        key_path = self.keys_dir / key_name
        
        if not key_path.exists() or not key_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"SSH key '{key_name}' not found"
            )
        
        # Get fingerprint
        result = subprocess.run(
            ["ssh-keygen", "-l", "-f", str(key_path)],
            capture_output=True,
            text=True
        )
        
        fingerprint = result.stdout.strip() if result.returncode == 0 else "Unknown"
        
        # Check for public key
        pub_key_path = key_path.with_suffix(".pub")
        has_public_key = pub_key_path.exists()
        
        # Read public key if it exists
        public_key_content = None
        if has_public_key:
            public_key_content = pub_key_path.read_text().strip()
        
        return {
            "key_name": key_name,
            "fingerprint": fingerprint,
            "has_public_key": has_public_key,
            "public_key": public_key_content,
            "path": str(key_path)
        }
    
    def delete_key(self, key_name: str) -> dict:
        """
        Delete an SSH key.
        
        Args:
            key_name: Name of the key to delete
        
        Returns:
            Deletion confirmation dict
        
        Raises:
            HTTPException: If key not found
        """
        key_path = self.keys_dir / key_name
        
        if not key_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"SSH key '{key_name}' not found"
            )
        
        # Delete private key
        key_path.unlink()
        
        # Delete public key if exists
        pub_key_path = key_path.with_suffix(".pub")
        if pub_key_path.exists():
            pub_key_path.unlink()
        
        return {
            "key_name": key_name,
            "deleted": True
        }
    
    def get_ssh_command_args(self, key_name: Optional[str] = None) -> list[str]:
        """
        Get SSH command arguments for Git operations.
        
        Args:
            key_name: Optional specific key to use
        
        Returns:
            List of SSH command arguments
        """
        ssh_args = []
        
        if key_name:
            key_path = self.keys_dir / key_name
            if not key_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"SSH key '{key_name}' not found"
                )
            ssh_args = ["-i", str(key_path)]
        
        # Add strict host key checking options
        ssh_args.extend([
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"UserKnownHostsFile={self.known_hosts_path}"
        ])
        
        return ssh_args
    
    def configure_git_ssh(self, key_name: Optional[str] = None) -> dict:
        """
        Configure Git to use SSH with specified key.
        
        Args:
            key_name: Optional specific key to use
        
        Returns:
            Configuration details
        """
        ssh_args = self.get_ssh_command_args(key_name)
        ssh_command = f"ssh {' '.join(ssh_args)}"
        
        # Set GIT_SSH_COMMAND environment variable
        os.environ["GIT_SSH_COMMAND"] = ssh_command
        
        return {
            "ssh_command": ssh_command,
            "key_used": key_name,
            "configured": True
        }
