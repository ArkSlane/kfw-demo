"""
Tests for SSHKeyManager class.
"""
import pytest
from pathlib import Path
import stat
import os
import platform
from ssh_manager import SSHKeyManager
from fastapi import HTTPException


def test_ssh_manager_initialization(ssh_keys_dir):
    """Test SSH key manager initialization."""
    manager = SSHKeyManager(ssh_keys_dir)
    
    assert manager.keys_dir == ssh_keys_dir
    assert manager.keys_dir.exists()
    assert manager.ssh_config_path == ssh_keys_dir / "config"
    assert manager.known_hosts_path == ssh_keys_dir / "known_hosts"


def test_add_key_success(ssh_manager, valid_private_key, ssh_keys_dir):
    """Test adding a valid SSH key."""
    result = ssh_manager.add_key("test_key", valid_private_key)
    
    assert result["key_name"] == "test_key"
    assert "fingerprint" in result
    assert result["has_public_key"] is False
    assert result["path"] == str(ssh_keys_dir / "test_key")
    
    # Verify file was created
    key_path = ssh_keys_dir / "test_key"
    assert key_path.exists()
    
    # Skip permission check on Windows (permissions work differently)
    if platform.system() != "Windows":
        key_stat = os.stat(key_path)
        mode = stat.S_IMODE(key_stat.st_mode)
        assert mode == 0o600


def test_add_key_with_public_key(ssh_manager, valid_private_key, valid_public_key, ssh_keys_dir):
    """Test adding SSH key with public key."""
    result = ssh_manager.add_key("test_key", valid_private_key, valid_public_key)
    
    assert result["key_name"] == "test_key"
    assert result["has_public_key"] is True
    
    # Verify both files were created
    private_key_path = ssh_keys_dir / "test_key"
    public_key_path = ssh_keys_dir / "test_key.pub"
    
    assert private_key_path.exists()
    assert public_key_path.exists()
    
    # Skip permission check on Windows (permissions work differently)
    if platform.system() != "Windows":
        private_stat = os.stat(private_key_path)
        private_mode = stat.S_IMODE(private_stat.st_mode)
        assert private_mode == 0o600
        
        public_stat = os.stat(public_key_path)
        public_mode = stat.S_IMODE(public_stat.st_mode)
        assert public_mode == 0o644


def test_add_key_invalid_name(ssh_manager, valid_private_key):
    """Test adding key with invalid name."""
    with pytest.raises(HTTPException) as exc_info:
        ssh_manager.add_key("invalid/name", valid_private_key)
    
    assert exc_info.value.status_code == 400
    assert "alphanumeric" in str(exc_info.value.detail).lower()


def test_add_key_invalid_format(ssh_manager):
    """Test adding key with invalid format."""
    with pytest.raises(HTTPException) as exc_info:
        ssh_manager.add_key("test_key", "not a valid key")
    
    assert exc_info.value.status_code == 400
    assert "invalid private key format" in str(exc_info.value.detail).lower()


def test_add_key_duplicate(ssh_manager, valid_private_key):
    """Test adding duplicate key."""
    # Add first key
    ssh_manager.add_key("duplicate", valid_private_key)
    
    # Try to add again
    with pytest.raises(HTTPException) as exc_info:
        ssh_manager.add_key("duplicate", valid_private_key)
    
    assert exc_info.value.status_code == 409
    assert "already exists" in str(exc_info.value.detail)


def test_list_keys_empty(ssh_manager):
    """Test listing keys when none exist."""
    keys = ssh_manager.list_keys()
    
    assert isinstance(keys, list)
    assert len(keys) == 0


def test_list_keys_multiple(ssh_manager, valid_private_key):
    """Test listing multiple keys."""
    # Add multiple keys
    ssh_manager.add_key("key1", valid_private_key)
    ssh_manager.add_key("key2", valid_private_key)
    ssh_manager.add_key("key3", valid_private_key)
    
    keys = ssh_manager.list_keys()
    
    assert len(keys) == 3
    key_names = [k["key_name"] for k in keys]
    assert "key1" in key_names
    assert "key2" in key_names
    assert "key3" in key_names


def test_get_key_success(ssh_manager, valid_private_key, valid_public_key):
    """Test getting key details."""
    # Add a key
    ssh_manager.add_key("test_key", valid_private_key, valid_public_key)
    
    # Get key details
    result = ssh_manager.get_key("test_key")
    
    assert result["key_name"] == "test_key"
    assert "fingerprint" in result
    assert result["has_public_key"] is True
    assert "public_key" in result
    assert result["public_key"].strip() == valid_public_key.strip()


def test_get_key_not_found(ssh_manager):
    """Test getting non-existent key."""
    with pytest.raises(HTTPException) as exc_info:
        ssh_manager.get_key("nonexistent")
    
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail)


def test_delete_key_success(ssh_manager, valid_private_key, ssh_keys_dir):
    """Test deleting a key."""
    # Add a key
    ssh_manager.add_key("delete_me", valid_private_key)
    
    key_path = ssh_keys_dir / "delete_me"
    assert key_path.exists()
    
    # Delete the key
    result = ssh_manager.delete_key("delete_me")
    
    assert result["key_name"] == "delete_me"
    assert result["deleted"] is True
    assert not key_path.exists()


def test_delete_key_with_public_key(ssh_manager, valid_private_key, valid_public_key, ssh_keys_dir):
    """Test deleting key with public key."""
    # Add key with public key
    ssh_manager.add_key("delete_both", valid_private_key, valid_public_key)
    
    private_path = ssh_keys_dir / "delete_both"
    public_path = ssh_keys_dir / "delete_both.pub"
    assert private_path.exists()
    assert public_path.exists()
    
    # Delete the key
    ssh_manager.delete_key("delete_both")
    
    # Both should be deleted
    assert not private_path.exists()
    assert not public_path.exists()


def test_delete_key_not_found(ssh_manager):
    """Test deleting non-existent key."""
    with pytest.raises(HTTPException) as exc_info:
        ssh_manager.delete_key("nonexistent")
    
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail)


def test_get_ssh_command_args_no_key(ssh_manager):
    """Test getting SSH command args without specific key."""
    args = ssh_manager.get_ssh_command_args()
    
    assert "-o" in args
    assert "StrictHostKeyChecking=accept-new" in args
    assert "UserKnownHostsFile" in " ".join(args)


def test_get_ssh_command_args_with_key(ssh_manager, valid_private_key, ssh_keys_dir):
    """Test getting SSH command args with specific key."""
    # Add a key
    ssh_manager.add_key("test_key", valid_private_key)
    
    args = ssh_manager.get_ssh_command_args("test_key")
    
    assert "-i" in args
    key_path_idx = args.index("-i") + 1
    assert args[key_path_idx] == str(ssh_keys_dir / "test_key")
    assert "-o" in args
    assert "StrictHostKeyChecking=accept-new" in args


def test_get_ssh_command_args_key_not_found(ssh_manager):
    """Test getting SSH command args with non-existent key."""
    with pytest.raises(HTTPException) as exc_info:
        ssh_manager.get_ssh_command_args("nonexistent")
    
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail)


def test_configure_git_ssh_no_key(ssh_manager):
    """Test configuring Git SSH without specific key."""
    result = ssh_manager.configure_git_ssh()
    
    assert result["configured"] is True
    assert "ssh_command" in result
    assert result["key_used"] is None
    assert "GIT_SSH_COMMAND" in os.environ


def test_configure_git_ssh_with_key(ssh_manager, valid_private_key):
    """Test configuring Git SSH with specific key."""
    # Add a key
    ssh_manager.add_key("test_key", valid_private_key)
    
    result = ssh_manager.configure_git_ssh("test_key")
    
    assert result["configured"] is True
    assert result["key_used"] == "test_key"
    assert "-i" in result["ssh_command"]
    assert "test_key" in result["ssh_command"]
    assert "GIT_SSH_COMMAND" in os.environ
    assert "test_key" in os.environ["GIT_SSH_COMMAND"]
