import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from enum import Enum
from dataclasses import dataclass
import subprocess
import tempfile
import shutil
from git import GitRepo

class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"

@dataclass
class TestImpact:
    test_name: str
    file_path: str
    change_type: ChangeType
    lines_changed: Optional[List[int]] = None
    impacted_by_helper: Optional[str] = None

class TestAnalyzer:
    def __init__(self):
        # Regex to match test definitions in Playwright/TypeScript files
        self.test_patterns = [
            r'test\([\'"](.+?)[\'"]',  # test('test name')
            r'it\([\'"](.+?)[\'"]',     # it('test name')
        ]
        
    def extract_tests_with_lines(self, content: str) -> Dict[str, Tuple[int, int]]:
        """
        Extract test names with their start and end line numbers.
        Returns dict: {test_name: (start_line, end_line)}
        """
        tests = {}
        lines = content.split('\n')
        
        # Find test blocks
        for i, line in enumerate(lines, 1):
            for pattern in self.test_patterns:
                match = re.search(pattern, line)
                if match:
                    test_name = match.group(1)
                    # Find the end of this test (next test or end of file)
                    end_line = self._find_test_end(lines, i)
                    tests[test_name] = (i, end_line)
        
        return tests
    
    def _find_test_end(self, lines: List[str], start_line: int) -> int:
        """Find the line number where the test ends."""
        brace_count = 0
        in_test = False
        
        for i in range(start_line - 1, len(lines)):
            line = lines[i]
            
            # Count opening and closing braces
            brace_count += line.count('{')
            brace_count -= line.count('}')
            
            if brace_count > 0:
                in_test = True
            elif in_test and brace_count == 0:
                # We've found the closing brace of the test
                return i + 1
        
        return len(lines)
    
    def analyze_file_changes(
        self, 
        repo: GitRepo,
        commit_sha: str,
        file_path: str,
        status: str
    ) -> List[TestImpact]:
        """Analyze test changes in a specific file."""
        impacts = []
        
        # Get current and previous file content
        current_content = repo.get_file_content(commit_sha, file_path)
        parent_commit = repo.get_parent_commit(commit_sha)
        previous_content = repo.get_file_content(parent_commit, file_path) if parent_commit else ""
        
        # Extract tests with line numbers
        current_tests = self.extract_tests_with_lines(current_content)
        previous_tests = self.extract_tests_with_lines(previous_content)
        
        # Get changed line numbers
        changed_lines = repo.get_changed_lines(commit_sha, file_path)
        
        # Handle file additions/deletions
        if status == 'A':  # New file, all tests are added
            for test_name, (start, end) in current_tests.items():
                impacts.append(TestImpact(
                    test_name=test_name,
                    file_path=file_path,
                    change_type=ChangeType.ADDED
                ))
        elif status == 'D':  # Deleted file, all tests are removed
            for test_name, (start, end) in previous_tests.items():
                impacts.append(TestImpact(
                    test_name=test_name,
                    file_path=file_path,
                    change_type=ChangeType.REMOVED
                ))
        else:  # Modified file - need to analyze which tests were affected
            # Find added tests (in current but not in previous)
            for test_name in set(current_tests.keys()) - set(previous_tests.keys()):
                impacts.append(TestImpact(
                    test_name=test_name,
                    file_path=file_path,
                    change_type=ChangeType.ADDED
                ))
            
            # Find removed tests (in previous but not in current)
            for test_name in set(previous_tests.keys()) - set(current_tests.keys()):
                impacts.append(TestImpact(
                    test_name=test_name,
                    file_path=file_path,
                    change_type=ChangeType.REMOVED
                ))
            
            # Find modified tests (exist in both but have changed lines within them)
            common_tests = set(current_tests.keys()).intersection(set(previous_tests.keys()))
            for test_name in common_tests:
                # Get test boundaries from current version
                current_start, current_end = current_tests[test_name]
                
                # Check if any changed line falls within this test
                test_changed_lines = [
                    line for line in changed_lines 
                    if current_start <= line <= current_end
                ]
                
                if test_changed_lines:
                    impacts.append(TestImpact(
                        test_name=test_name,
                        file_path=file_path,
                        change_type=ChangeType.MODIFIED,
                        lines_changed=test_changed_lines
                    ))
        
        return impacts
