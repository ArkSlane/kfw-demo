"""
Input validation and sanitization for Git service.
Prevents path traversal, command injection, and other security issues.
"""
import re
from pathlib import Path
from typing import Optional
from fastapi import HTTPException


# Security patterns
DANGEROUS_PATH_PATTERNS = [
    r'\.\.',  # Parent directory references
    r'~',     # Home directory
    r'\$',    # Shell variables
    r'`',     # Command substitution
    r'\|',    # Pipe
    r';',     # Command separator
    r'&',     # Background execution
    r'\n',    # Newline injection
    r'\r',    # Carriage return injection
]

VALID_BRANCH_PATTERN = re.compile(r'^[a-zA-Z0-9/_.-]+$')
INVALID_BRANCH_SEQUENCES = [
    '..',     # Parent reference
    '//',     # Double slash
    '@{',     # Special git ref
    '~',      # Tilde expansion
]

# Maximum lengths to prevent DoS
MAX_COMMIT_MESSAGE_LENGTH = 10000
MAX_BRANCH_NAME_LENGTH = 255
MAX_FILE_PATH_LENGTH = 4096


def sanitize_path(path_str: str, base_path: Path) -> Path:
    """
    Sanitize and validate a file path to prevent path traversal attacks.
    
    Args:
        path_str: The user-provided path string
        base_path: The base directory that paths must be within
        
    Returns:
        Resolved absolute Path object
        
    Raises:
        HTTPException: If path is invalid or attempts traversal
    """
    if not path_str:
        raise HTTPException(status_code=400, detail="Path cannot be empty")
    
    if len(path_str) > MAX_FILE_PATH_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Path too long (max {MAX_FILE_PATH_LENGTH} characters)"
        )
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATH_PATTERNS:
        if re.search(pattern, path_str):
            raise HTTPException(
                status_code=400,
                detail=f"Path contains invalid characters or sequences: {pattern}"
            )
    
    # Resolve the path
    try:
        # Convert to Path and resolve to absolute path
        user_path = Path(path_str)
        
        # If it's absolute, reject it (should be relative to base)
        if user_path.is_absolute():
            raise HTTPException(
                status_code=400,
                detail="Absolute paths are not allowed"
            )
        
        # Resolve the full path
        full_path = (base_path / user_path).resolve()
        
        # Ensure the resolved path is still within base_path
        try:
            full_path.relative_to(base_path)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Path traversal detected: path escapes workspace directory"
            )
        
        return full_path
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=400,
            detail=f"Invalid path: {str(e)}"
        )


def validate_branch_name(branch_name: str) -> str:
    """
    Validate a Git branch name to prevent command injection.
    
    Git branch name rules:
    - Can contain alphanumerics, slashes, hyphens, underscores, dots
    - Cannot contain .., //, spaces, or special shell characters
    - Cannot start with - (would be interpreted as flag)
    - Cannot be just . or @
    
    Args:
        branch_name: The branch name to validate
        
    Returns:
        The validated branch name (unchanged if valid)
        
    Raises:
        HTTPException: If branch name is invalid
    """
    if not branch_name:
        raise HTTPException(status_code=400, detail="Branch name cannot be empty")
    
    if len(branch_name) > MAX_BRANCH_NAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Branch name too long (max {MAX_BRANCH_NAME_LENGTH} characters)"
        )
    
    # Check if starts with dash (would be interpreted as flag)
    if branch_name.startswith('-'):
        raise HTTPException(
            status_code=400,
            detail="Branch name cannot start with '-'"
        )
    
    # Check for invalid sequences
    for seq in INVALID_BRANCH_SEQUENCES:
        if seq in branch_name:
            raise HTTPException(
                status_code=400,
                detail=f"Branch name contains invalid sequence: {seq}"
            )
    
    # Check against allowed pattern
    if not VALID_BRANCH_PATTERN.match(branch_name):
        raise HTTPException(
            status_code=400,
            detail="Branch name contains invalid characters (allowed: a-z, A-Z, 0-9, /, _, -, .)"
        )
    
    # Additional checks
    if branch_name in ['.', '@', 'HEAD']:
        raise HTTPException(
            status_code=400,
            detail=f"Reserved branch name: {branch_name}"
        )
    
    if branch_name.endswith('.lock'):
        raise HTTPException(
            status_code=400,
            detail="Branch name cannot end with '.lock'"
        )
    
    return branch_name


def validate_commit_message(message: str) -> str:
    """
    Validate a commit message for length and encoding.
    
    Args:
        message: The commit message to validate
        
    Returns:
        The validated message (unchanged if valid)
        
    Raises:
        HTTPException: If message is invalid
    """
    if not message:
        raise HTTPException(status_code=400, detail="Commit message cannot be empty")
    
    if len(message) > MAX_COMMIT_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Commit message too long (max {MAX_COMMIT_MESSAGE_LENGTH} characters)"
        )
    
    # Check for null bytes (can cause issues with git)
    if '\0' in message:
        raise HTTPException(
            status_code=400,
            detail="Commit message cannot contain null bytes"
        )
    
    # Ensure it's valid UTF-8
    try:
        message.encode('utf-8')
    except UnicodeEncodeError:
        raise HTTPException(
            status_code=400,
            detail="Commit message must be valid UTF-8"
        )
    
    # Check for control characters (except newlines and tabs)
    for char in message:
        if ord(char) < 32 and char not in ['\n', '\t', '\r']:
            raise HTTPException(
                status_code=400,
                detail=f"Commit message contains invalid control character: {repr(char)}"
            )
    
    return message


def validate_file_list(files: list[str], base_path: Path) -> list[str]:
    """
    Validate a list of file paths.
    
    Args:
        files: List of file paths to validate
        base_path: Base directory for path validation
        
    Returns:
        List of validated file paths (relative to base_path)
        
    Raises:
        HTTPException: If any file path is invalid
    """
    if not files:
        raise HTTPException(status_code=400, detail="File list cannot be empty")
    
    if len(files) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Too many files (max 1000 per request)"
        )
    
    validated_files = []
    for file_path in files:
        # Sanitize each path
        full_path = sanitize_path(file_path, base_path)
        
        # Store relative path for git command
        relative_path = full_path.relative_to(base_path)
        validated_files.append(str(relative_path))
    
    return validated_files


def validate_repo_url(repo_url: str) -> str:
    """
    Validate a Git repository URL.
    
    Args:
        repo_url: The repository URL to validate
        
    Returns:
        The validated URL
        
    Raises:
        HTTPException: If URL is invalid
    """
    if not repo_url:
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty")
    
    if len(repo_url) > 2048:
        raise HTTPException(
            status_code=400,
            detail="Repository URL too long (max 2048 characters)"
        )
    
    # Allow https://, git://, and SSH URLs (git@...)
    is_https = repo_url.startswith('https://')
    is_git = repo_url.startswith('git://')
    is_ssh = repo_url.startswith('git@')
    
    if not (is_https or is_git or is_ssh):
        raise HTTPException(
            status_code=400,
            detail="Only https://, git://, and SSH (git@...) protocols are allowed"
        )
    
    # Check for dangerous characters (excluding @ and : which are valid in SSH URLs)
    dangerous_chars = ['`', '$', ';', '&', '|', '\n', '\r']
    for char in dangerous_chars:
        if char in repo_url:
            raise HTTPException(
                status_code=400,
                detail=f"Repository URL contains invalid character: {char}"
            )
    
    return repo_url


def validate_target_dir(target_dir: Optional[str], base_path: Path) -> Optional[Path]:
    """
    Validate a target directory for cloning.
    
    Args:
        target_dir: The target directory name (relative)
        base_path: The base workspace path
        
    Returns:
        Validated Path object or None
        
    Raises:
        HTTPException: If directory name is invalid
    """
    if target_dir is None:
        return None
    
    # Sanitize the path
    validated_path = sanitize_path(target_dir, base_path)
    
    # Additional check: should be a direct child (no subdirectories)
    if '/' in target_dir or '\\' in target_dir:
        raise HTTPException(
            status_code=400,
            detail="Target directory must be a direct child of workspace (no subdirectories)"
        )
    
    return validated_path
