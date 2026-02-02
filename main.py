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
from test_impact_analyzer import TestImpactAnalyzer 

def main():
    parser = argparse.ArgumentParser(
        description='Analyze test impact for commits in flash-tests repository'
    )
    parser.add_argument(
        '--commit',
        required=True,
        help='Commit SHA to analyze'
    )
    parser.add_argument(
        '--repo',
        help='Path to local flash-tests repository (optional, will clone if not provided)'
    )
    parser.add_argument(
        '--repo-url',
        default='https://github.com/empiricalrun/flash-tests.git',
        help='GitHub repository URL (default: flash-tests)'
    )
    
    args = parser.parse_args()
    
    # Get repository path
    if args.repo and os.path.exists(args.repo):
        repo_path = args.repo
    else:
        print("Cloning repository...")
        repo_path = clone_repo(args.repo_url)
    
    # Analyze commit
    analyzer = TestImpactAnalyzer()
    impacts = analyzer.analyze_commit(repo_path, args.commit)
    analyzer.print_results(impacts)
    
    # Cleanup if we cloned to temp directory
    if not args.repo and repo_path.startswith(tempfile.gettempdir()):
        print(f"\nRepository cloned to temporary directory: {repo_path}")
        print("This directory will not be automatically deleted.")


if __name__ == "__main__":
    main()
