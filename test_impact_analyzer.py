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
from analyze_direct_changes import HelperAnalyzer

class TestImpactAnalyzer:
    def __init__(self):
        self.repo = None
        self.test_analyzer = TestAnalyzer()
        self.helper_analyzer = HelperAnalyzer()
    
    def analyze_commit(self, repo_path: str, commit_sha: str) -> List[TestImpact]:
        """Analyze test impacts for a given commit."""
        print(f"Analyzing commit: {commit_sha}")
        print(f"Repository: {repo_path}")
        
        self.repo = GitRepo(repo_path)
        
        # Get changed files in the commit
        changed_files = self.repo.get_commit_files(commit_sha)
        
        if not changed_files:
            print("No files changed in this commit.")
            return []
        
        print(f"Total files changed: {len(changed_files)}")
        
        # Separate test files and helper files
        test_files = []
        helper_files = []
        
        for status, file_path in changed_files:
            if file_path.endswith('.spec.ts'):
                test_files.append((status, file_path))
            elif file_path.endswith(('.ts', '.js')):
                helper_files.append((status, file_path))
        
        print(f"Test files changed: {len(test_files)}")
        print(f"Helper files changed: {len(helper_files)}")
        
        all_impacts = []
        
        # 1. Analyze direct test file changes
        for status, file_path in test_files:
            print(f"\nAnalyzing test file: {file_path} ({status})")
            impacts = self.test_analyzer.analyze_file_changes(
                self.repo, commit_sha, file_path, status
            )
            all_impacts.extend(impacts)
            
            if impacts:
                print(f"  Found {len(impacts)} impacted tests")
        
        # 2. Analyze helper file changes and their impact on tests
        for status, file_path in helper_files:
            print(f"\nAnalyzing helper file: {file_path} ({status})")
            
            # Analyze helper functions and find impacted tests
            impacts = self.helper_analyzer.analyze_helper_file_changes(
                self.repo, commit_sha, file_path, status
            )
            all_impacts.extend(impacts)
        
        return all_impacts

    def print_results(self, impacts: List[TestImpact]):
        """Print analysis results in a readable format with colorful icons."""
        # ANSI color codes
        RESET = "\033[0m"
        BOLD = "\033[1m"
        
        # Title colors
        TITLE_COLOR = "\033[38;5;33m"  # Blue
        SUCCESS_COLOR = "\033[38;5;40m"  # Green
        COUNT_COLOR = "\033[38;5;208m"  # Orange
        
        # Section colors
        SECTION_COLOR = "\033[38;5;141m"  # Purple
        SUMMARY_COLOR = "\033[38;5;220m"  # Yellow
        
        # Change type colors
        ADDED_COLOR = "\033[38;5;46m"  # Bright Green
        MODIFIED_COLOR = "\033[38;5;226m"  # Yellow
        REMOVED_COLOR = "\033[38;5;196m"  # Red
        
        # Helper colors
        HELPER_COLOR = "\033[38;5;214m"  # Orange
        FILE_COLOR = "\033[38;5;81m"  # Cyan
        LINES_COLOR = "\033[38;5;213m"  # Pink
        
        # Icon colors
        ICON_TITLE = "\033[38;5;39m"  # Light Blue
        ICON_SUCCESS = "\033[38;5;48m"  # Bright Green
        ICON_COUNT = "\033[38;5;208m"  # Orange
        ICON_SUMMARY = "\033[38;5;220m"  # Yellow
        ICON_DIRECT = "\033[38;5;141m"  # Purple
        ICON_ADDED = ADDED_COLOR
        ICON_MODIFIED = MODIFIED_COLOR
        ICON_REMOVED = REMOVED_COLOR
        ICON_HELPER = HELPER_COLOR
        ICON_FILE = FILE_COLOR
        ICON_COMPLETE = "\033[38;5;48m"  # Bright Green
        ICON_STATS = "\033[38;5;208m"  # Orange
        
        if not impacts:
            print("\n" + "="*80)
            print("NO TEST IMPACTS FOUND")
            print("="*80)
            return
        
        print("\n" + "="*80)
        print(f"{ICON_TITLE}{RESET}{TITLE_COLOR}{BOLD} TEST IMPACT ANALYSIS RESULTS{RESET}")
        print("="*80)
        
        # Remove duplicates - if a test is directly changed AND impacted by helper,
        # prioritize the direct change and remove the helper impact
        unique_impacts = []
        seen_tests = set()
        
        # First pass: add direct impacts
        for impact in impacts:
            if not impact.impacted_by_helper:
                test_key = f"{impact.file_path}:{impact.test_name}"
                if test_key not in seen_tests:
                    unique_impacts.append(impact)
                    seen_tests.add(test_key)
        
        # Second pass: add helper impacts only if not already seen as direct impact
        for impact in impacts:
            if impact.impacted_by_helper:
                test_key = f"{impact.file_path}:{impact.test_name}"
                if test_key not in seen_tests:
                    unique_impacts.append(impact)
                    seen_tests.add(test_key)
        
        impacts = unique_impacts
        
        print(f"{ICON_SUCCESS}{RESET} {SUCCESS_COLOR}Commit analyzed successfully!{RESET}")
        print(f"{ICON_COUNT}{RESET} {COUNT_COLOR}Total impacted tests: {len(impacts)}{RESET}")
        
        # Separate direct impacts from helper impacts
        direct_impacts = [i for i in impacts if not i.impacted_by_helper]
        helper_impacts = [i for i in impacts if i.impacted_by_helper]
        
        # Summary at the top
        print(f"\n{ICON_SUMMARY}{RESET} {SUMMARY_COLOR}{BOLD}SUMMARY:{RESET}")
        print(f"   {ICON_SUCCESS}{RESET} {SUCCESS_COLOR}Direct test changes: {len(direct_impacts)}{RESET}")
        print(f"   {ICON_HELPER}{RESET} {HELPER_COLOR}Helper file impacts: {len(helper_impacts)}{RESET}")
        print("-" * 40)
        
        # Group direct impacts by change type
        impacts_by_type = {}
        for impact in direct_impacts:
            impacts_by_type.setdefault(impact.change_type, []).append(impact)
        
        # Print direct impacts
        if direct_impacts:
            print(f"\n{ICON_DIRECT}{RESET} {SECTION_COLOR}{BOLD}DIRECT TEST CHANGES ({len(direct_impacts)}):{RESET}")
            print("-" * 60)
            
            for change_type in [ChangeType.ADDED, ChangeType.MODIFIED, ChangeType.REMOVED]:
                type_impacts = impacts_by_type.get(change_type, [])
                if type_impacts:
                    # Nerd Font icons for each change type with colors
                    icon_color = {
                        ChangeType.ADDED: ICON_ADDED,
                        ChangeType.MODIFIED: ICON_MODIFIED, 
                        ChangeType.REMOVED: ICON_REMOVED
                    }
                    text_color = {
                        ChangeType.ADDED: ADDED_COLOR,
                        ChangeType.MODIFIED: MODIFIED_COLOR,
                        ChangeType.REMOVED: REMOVED_COLOR
                    }
                    icon_char = {
                        ChangeType.ADDED: "",
                        ChangeType.MODIFIED: "", 
                        ChangeType.REMOVED: ""
                    }
                    
                    icon = icon_char[change_type]
                    color = icon_color[change_type]
                    text_color_val = text_color[change_type]
                    
                    print(f"\n{color}{icon}{RESET} {text_color_val}{BOLD}{change_type.value.upper()} TESTS ({len(type_impacts)}):{RESET}")
                    for i, impact in enumerate(type_impacts, 1):
                        print(f"   {i:2d}. {impact.test_name}")
                        print(f"       {ICON_FILE}{RESET} {FILE_COLOR}File: {impact.file_path}{RESET}")
                        if impact.lines_changed:
                            print(f"       {LINES_COLOR}{RESET} {LINES_COLOR}Changed lines: {impact.lines_changed}{RESET}")
                    print()  # Add spacing between change types
        
        # Print helper impacts
        if helper_impacts:
            print(f"\n{ICON_SUMMARY}{RESET} {SECTION_COLOR}{BOLD}TESTS IMPACTED BY HELPER CHANGES ({len(helper_impacts)}):{RESET}")
            print("-" * 60)
            
            # Group by helper function
            impacts_by_helper = {}
            for impact in helper_impacts:
                helper_name = impact.impacted_by_helper
                if helper_name not in impacts_by_helper:
                    impacts_by_helper[helper_name] = []
                impacts_by_helper[helper_name].append(impact)
            
            # Sort helpers by function name
            for helper_idx, helper in enumerate(sorted(impacts_by_helper.keys()), 1):
                helper_impacts_list = impacts_by_helper[helper]
                print(f"\n   {helper_idx}. {ICON_HELPER}{RESET} {HELPER_COLOR}{BOLD}Helper: {helper}{RESET}")
                print(f"      {COUNT_COLOR}Impacts {len(helper_impacts_list)} test(s):{RESET}")
                
                # Sort tests by file and test name
                helper_impacts_list.sort(key=lambda x: (x.file_path, x.test_name))
                for test_idx, impact in enumerate(helper_impacts_list, 1):
                    print(f"        {test_idx:2d}. {impact.test_name}")
                    print(f"            {ICON_FILE}{RESET} {FILE_COLOR}{impact.file_path}{RESET}")
        
        # Final summary
        print("\n" + "="*80)
        print(f"{ICON_COMPLETE}{RESET} {SUCCESS_COLOR}{BOLD}ANALYSIS COMPLETE{RESET}")
        print("="*80)
        print(f"{ICON_STATS}{RESET} {SUMMARY_COLOR}{BOLD}FINAL STATISTICS:{RESET}")
        print(f"   • {COUNT_COLOR}Total tests impacted: {len(impacts)}{RESET}")
        print(f"   • {SUCCESS_COLOR}Direct test changes: {len(direct_impacts)}{RESET}")
        print(f"   • {HELPER_COLOR}Tests impacted by helpers: {len(helper_impacts)}{RESET}")
        
        if direct_impacts:
            for change_type in [ChangeType.ADDED, ChangeType.MODIFIED, ChangeType.REMOVED]:
                type_impacts = impacts_by_type.get(change_type, [])
                if type_impacts:
                    icon_color = {
                        ChangeType.ADDED: ICON_ADDED,
                        ChangeType.MODIFIED: ICON_MODIFIED, 
                        ChangeType.REMOVED: ICON_REMOVED
                    }
                    text_color = {
                        ChangeType.ADDED: ADDED_COLOR,
                        ChangeType.MODIFIED: MODIFIED_COLOR,
                        ChangeType.REMOVED: REMOVED_COLOR
                    }
                    icon_char = {
                        ChangeType.ADDED: "",
                        ChangeType.MODIFIED: "", 
                        ChangeType.REMOVED: ""
                    }
                    print(f"   {icon_color[change_type]}{icon_char[change_type]}{RESET} {text_color[change_type]}{change_type.value.title()} tests: {len(type_impacts)}{RESET}")
        
        if helper_impacts:
            print(f"   {ICON_HELPER}{RESET} {HELPER_COLOR}Helpers modified: {len(impacts_by_helper)}{RESET}")
        
        print("="*80)


