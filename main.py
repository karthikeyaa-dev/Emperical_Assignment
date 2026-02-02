import os
import sys
import argparse
import subprocess
import tempfile
import shutil
from test_impact_analyzer import TestImpactAnalyzer

def clone_repo(repo_url: str, local_path: str = None) -> str:
    """
    Clone the repository if local_path is not provided.
    Returns the path to the repository.
    """
    if local_path and os.path.exists(local_path):
        print(f"Using existing repository at: {local_path}")
        return local_path
    
    # Create temporary directory for clone
    temp_dir = tempfile.mkdtemp(prefix="flash-tests-")
    print(f"Cloning repository to temporary directory: {temp_dir}")
    
    try:
        subprocess.run(
            ['git', 'clone', repo_url, temp_dir],
            check=True,
            capture_output=True,
            text=True
        )
        return temp_dir
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e.stderr}")
        shutil.rmtree(temp_dir)  # Cleanup if clone failed
        sys.exit(1)

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
    
    temp_repo_dir = None  # Will track temporary clone if needed

    # Determine repository path
    if args.repo and os.path.exists(args.repo):
        repo_path = args.repo
    else:
        repo_path = clone_repo(args.repo_url)
        temp_repo_dir = repo_path  # Mark for cleanup
    
    try:
        # Analyze the commit
        analyzer = TestImpactAnalyzer()
        impacts = analyzer.analyze_commit(repo_path, args.commit)
        analyzer.print_results(impacts)
    finally:
        # Cleanup temporary repository if we cloned it
        if temp_repo_dir and os.path.exists(temp_repo_dir):
            print(f"\nCleaning up temporary repository at: {temp_repo_dir}")
            shutil.rmtree(temp_repo_dir)

if __name__ == "__main__":
    main()
