from typing import List, Dict, Tuple, Set, Optional
from enum import Enum
from dataclasses import dataclass
import subprocess
import tempfile
import shutil
import re

class GitRepo:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        
    def get_commit_files(self, commit_sha: str) -> List[Tuple[str, str]]:
        """Get list of files changed in a commit with their change status."""
        try:
            cmd = ['git', 'diff', '--name-status', f'{commit_sha}^..{commit_sha}']
            result = subprocess.run(
                cmd, 
                cwd=self.repo_path, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    status, file_path = line.split('\t', 1)
                    files.append((status.strip(), file_path.strip()))
            return files
        except subprocess.CalledProcessError as e:
            print(f"Error getting commit files: {e}")
            return []

    def get_file_content(self, commit_sha: str, file_path: str) -> str:
        """Get file content at specific commit."""
        try:
            cmd = ['git', 'show', f'{commit_sha}:{file_path}']
            result = subprocess.run(
                cmd, 
                cwd=self.repo_path, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""

    def get_parent_commit(self, commit_sha: str) -> str:
        """Get parent commit SHA."""
        try:
            cmd = ['git', 'rev-parse', f'{commit_sha}^']
            result = subprocess.run(
                cmd, 
                cwd=self.repo_path, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""
    
    def get_file_diff(self, commit_sha: str, file_path: str) -> str:
        """Get unified diff for a specific file in commit."""
        try:
            parent_commit = self.get_parent_commit(commit_sha)
            cmd = ['git', 'diff', '--unified=0', f'{parent_commit}..{commit_sha}', '--', file_path]
            result = subprocess.run(
                cmd, 
                cwd=self.repo_path, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error getting diff for {file_path}: {e}")
            return ""
    
    def get_changed_lines(self, commit_sha: str, file_path: str) -> Set[int]:
        """Get set of line numbers that were changed in the commit."""
        diff_output = self.get_file_diff(commit_sha, file_path)
        changed_lines = set()
        
        # Parse unified diff output
        current_line = 0
        for line in diff_output.split('\n'):
            if line.startswith('@@'):
                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                match = re.search(r'@@ -\d+,?\d* \+(\d+),?\d* @@', line)
                if match:
                    current_line = int(match.group(1))
            elif line.startswith('+') and not line.startswith('+++'):
                # Added line
                changed_lines.add(current_line)
                current_line += 1
            elif line.startswith('-') and not line.startswith('---'):
                # Removed line
                changed_lines.add(current_line - 1)  # Line was in old file at this position
                # Don't increment current_line for deletions
            elif not line.startswith('-') and not line.startswith('+'):
                # Context line
                current_line += 1
        
        return changed_lines
    
    def get_all_test_files(self) -> List[str]:
        """Get all test files in the repository."""
        try:
            cmd = ['git', 'ls-files', '*.spec.ts']
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            files = result.stdout.strip().split('\n')
            return [f for f in files if f]
        except subprocess.CalledProcessError as e:
            print(f"Error getting test files: {e}")
            return []
