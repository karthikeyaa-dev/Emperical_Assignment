#!/usr/bin/env python3
"""
Test Impact Analyzer for Flash-Tests Repository - SIMPLIFIED VERSION

This tool analyzes which tests were impacted by a given commit.
It detects added, modified, and removed tests in Playwright test files.
"""

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
from test_analyzer import TestAnalyzer, TestImpact, ChangeType


class HelperAnalyzer:
    """Simplified helper analyzer - just search for function usage in test files."""
    
    def __init__(self):
        # Common JavaScript/TypeScript keywords to exclude
        self.js_keywords = {
            'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
            'break', 'continue', 'return', 'function', 'class', 'interface',
            'extends', 'implements', 'import', 'export', 'from', 'as',
            'const', 'let', 'var', 'typeof', 'instanceof', 'new', 'delete',
            'void', 'this', 'super', 'try', 'catch', 'finally', 'throw',
            'debugger', 'with', 'yield', 'await', 'async', 'static',
            'public', 'private', 'protected', 'readonly', 'abstract',
            'enum', 'type', 'namespace', 'module', 'require',
            'true', 'false', 'null', 'undefined', 'NaN', 'Infinity'
        }
    
    def extract_functions_with_lines(self, content: str) -> Dict[str, Tuple[int, int]]:
        """
        Extract function names with their start and end line numbers.
        Returns dict: {function_name: (start_line, end_line)}
        """
        functions = {}
        lines = content.split('\n')
        
        # Function patterns with start position
        function_patterns = [
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',  # function funcName or async function funcName
            r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',  # const funcName = () => or const funcName = async () =>
            r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?function\b',  # const funcName = function or const funcName = async function
        ]
        
        # Find function blocks
        for i, line in enumerate(lines, 1):
            for pattern in function_patterns:
                match = re.search(pattern, line)
                if match:
                    func_name = match.group(1)
                    if func_name and func_name.lower() not in self.js_keywords:
                        # Find the end of this function
                        end_line = self._find_function_end(lines, i)
                        functions[func_name] = (i, end_line)
        
        return functions
    
    def _find_function_end(self, lines: List[str], start_line: int) -> int:
        """Find the line number where the function ends."""
        brace_count = 0
        in_function = False
        
        for i in range(start_line - 1, len(lines)):
            line = lines[i]
            
            # Count opening and closing braces
            brace_count += line.count('{')
            brace_count -= line.count('}')
            
            if brace_count > 0:
                in_function = True
            elif in_function and brace_count == 0:
                # We've found the closing brace of the function
                return i + 1
        
        return len(lines)
    
    def find_changed_functions(self, repo: GitRepo, commit_sha: str, file_path: str) -> List[str]:
        """Find which functions were actually changed in the commit."""
        changed_functions = []
        
        # Get current and previous file content
        current_content = repo.get_file_content(commit_sha, file_path)
        parent_commit = repo.get_parent_commit(commit_sha)
        previous_content = repo.get_file_content(parent_commit, file_path) if parent_commit else ""
        
        if not current_content or not previous_content:
            return changed_functions
        
        # Extract functions with line numbers from both versions
        current_functions = self.extract_functions_with_lines(current_content)
        previous_functions = self.extract_functions_with_lines(previous_content)
        
        # Get changed line numbers
        changed_lines = repo.get_changed_lines(commit_sha, file_path)
        
        print(f"    Changed lines in file: {sorted(changed_lines)}")
        
        # Check which functions have changed lines within them
        for func_name, (start_line, end_line) in current_functions.items():
            # Check if any changed line falls within this function
            func_changed_lines = [
                line for line in changed_lines 
                if start_line <= line <= end_line
            ]
            
            if func_changed_lines:
                print(f"    Function '{func_name}' changed (lines {start_line}-{end_line})")
                changed_functions.append(func_name)
        
        # Also check for functions that were added or removed
        current_func_names = set(current_functions.keys())
        previous_func_names = set(previous_functions.keys())
        
        # Added functions
        for func_name in current_func_names - previous_func_names:
            if func_name not in changed_functions:
                print(f"    Function '{func_name}' was added")
                changed_functions.append(func_name)
        
        # Removed functions
        for func_name in previous_func_names - current_func_names:
            if func_name not in changed_functions:
                print(f"    Function '{func_name}' was removed")
                changed_functions.append(func_name)
        
        return changed_functions
    
    def find_tests_using_functions(self, repo: GitRepo, helper_file: str, functions: List[str]) -> List[TestImpact]:
        """Find tests that use any of the functions."""
        impacted_tests = []
        
        if not functions:
            print(f"    No changed functions found")
            return impacted_tests
        
        print(f"    Searching for changed functions: {', '.join(functions)}")
        
        # Get all test files
        test_files = repo.get_all_test_files()
        print(f"    Found {len(test_files)} test files to search")
        
        test_count = 0
        found_count = 0
        
        for test_file in test_files:
            # Get test file content
            test_content = repo.get_file_content('HEAD', test_file)
            if not test_content:
                continue
            
            # Clean the test content
            test_content = test_content.replace('\r\n', '\n').replace('\r', '\n')
            
            # First, check if any of our functions are mentioned anywhere in the file
            file_uses_function = False
            for func in functions:
                # Use word boundary to avoid partial matches
                if re.search(fr'\b{re.escape(func)}\b', test_content):
                    file_uses_function = True
                    break
            
            if not file_uses_function:
                continue
            
            # Find tests in this file
            test_analyzer = TestAnalyzer()
            tests = test_analyzer.extract_tests_with_lines(test_content)
            
            if not tests:
                continue
            
            # Check each test for function usage
            lines = test_content.split('\n')
            for test_name, (start_line, end_line) in tests.items():
                test_count += 1
                
                # Get the content of this specific test (1-indexed to 0-indexed conversion)
                test_lines = lines[start_line-1:end_line]
                test_block = '\n'.join(test_lines)
                
                # Check if any function is used in this test
                for func in functions:
                    # Look for function calls with proper word boundaries
                    # Pattern: function name followed by '(' or '.'
                    pattern = fr'\b{re.escape(func)}\s*(?:\(|\.)'
                    
                    if re.search(pattern, test_block):
                        found_count += 1
                        impacted_tests.append(TestImpact(
                            test_name=test_name.strip(),
                            file_path=test_file,
                            change_type=ChangeType.MODIFIED,
                            impacted_by_helper=f"{helper_file}:{func}"
                        ))
                        # Don't break - a test might use multiple functions
                        # Just mark it once for each function
        
        print(f"    Searched through {test_count} tests, found {found_count} function usages")
        return impacted_tests
    
    def analyze_helper_file_changes(self, repo: GitRepo, commit_sha: str, file_path: str, status: str) -> List[TestImpact]:
        """Analyze helper file changes and find impacted tests."""
        impacts = []
        
        print(f"    Analyzing helper file: {file_path}")
        
        if status == 'A':  # New file
            print(f"    New file - all functions are considered 'changed'")
            current_content = repo.get_file_content(commit_sha, file_path)
            if current_content:
                functions_dict = self.extract_functions_with_lines(current_content)
                functions = list(functions_dict.keys())
                print(f"    Found {len(functions)} function(s) in new file: {', '.join(functions)}")
            else:
                functions = []
        elif status == 'D':  # Deleted file
            print(f"    Deleted file - all functions are considered 'changed'")
            parent_commit = repo.get_parent_commit(commit_sha)
            previous_content = repo.get_file_content(parent_commit, file_path)
            if previous_content:
                functions_dict = self.extract_functions_with_lines(previous_content)
                functions = list(functions_dict.keys())
                print(f"    Found {len(functions)} function(s) in deleted file: {', '.join(functions)}")
            else:
                functions = []
        else:  # Modified file
            # Find which specific functions were changed
            functions = self.find_changed_functions(repo, commit_sha, file_path)
        
        if functions:
            print(f"    Found {len(functions)} changed function(s): {', '.join(functions)}")
            
            # Find tests that use these functions
            impacted_tests = self.find_tests_using_functions(repo, file_path, functions)
            
            if impacted_tests:
                print(f"    Found {len(impacted_tests)} test(s) using these changed functions")
                impacts.extend(impacted_tests)
            else:
                print(f"    No tests found using these changed functions")
        else:
            print(f"    No changed functions found in {file_path}")
        
        return impacts



