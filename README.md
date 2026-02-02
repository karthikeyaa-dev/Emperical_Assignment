# Test Impact Analyzer

## How It Works

This tool analyzes git commits to find which tests were impacted. Here's the simple breakdown:

### 1. **Git Diff Analysis**
- Uses `git diff` to see what changed in the commit
- Looks at added/modified/deleted files
- Tracks exact line numbers that changed

### 2. **Test Detection**
- Scans `.spec.ts` files for test patterns like `test('name')` and `it('name')`
- Maps each test to its start and end lines
- When lines change inside a test's range → test was modified

### 3. **Helper Function Tracking**
- Finds JavaScript/TypeScript functions in `.ts`/.`.js` files
- When helper functions change, searches all test files for usage
- Uses word boundaries to find where tests call these functions

### 4. **Impact Analysis**
- **Direct changes**: Tests that were edited directly
- **Helper impacts**: Tests that use changed helper functions
- **File operations**: Tests in added/deleted files

## Techniques Used

1. **Git Operations**: `git diff`, `git show`, `git log` for commit analysis
2. **Regex Patterns**: Finds tests/functions in source code
3. **Line Mapping**: Tracks which lines belong to which tests/functions
4. **Cross-referencing**: Links helper functions to tests that use them


## Quick Start

1. **Clone this repo**
```bash
git clone <this-repo-url>
cd Empirical_Assigment
```

2. **Option 1: With Local Repository**
```bash
# Clone the flash-tests repo first
git clone https://github.com/empiricalrun/flash-tests.git

# Run the analyzer
uv run main.py --commit <commit_id> --repo /path/to/flash-tests
# or
python main.py --commit <commit_id> --repo /path/to/flash-tests
```

3. **Option 2: Let It Clone Automatically**
```bash
# Just provide the commit ID and URL
uv run main.py --commit <commit_id> --repo-url https://github.com/empiricalrun/flash-tests.git
# or
python main.py --commit <commit_id> --repo-url https://github.com/empiricalrun/flash-tests.git
```
## Requirements
- Python 3.7+
- Git installed
- UV (optional, but recommended) or standard Python

## How It Works
The tool analyzes git commits to find which tests were impacted by code changes. It detects:
- Direct test modifications in `.spec.ts` files
- Tests affected by helper/utility function changes
- Added/removed tests

## Output
Shows a summary of impacted tests, including:
- Direct test changes (added/modified/removed)
- Tests impacted via helper function changes
- File paths and line numbers

## Troubleshooting
- Ensure the commit ID exists in the repository
- Make sure Git is installed and accessible

## Video

- Path: https://drive.google.com/file/d/1g2UUmOJ6XMaCmu8gFSKzP9oEIv66caRL/view?usp=sharing
