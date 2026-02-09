# ROS Newcomer Onboarding Analysis Dataset

This repository contains the dataset and pipeline for analyzing newcomer onboarding and participation in open-source ROS packages.

## Overview

This project explores onboarding of newcomers in open-source robotics repositories, specifically analyzing ROS packages across three active distributions: **ROS 2 Humble**, **ROS 2 Jazzy**, and **ROS 2 Kilted**.

**Paper**: Submitted to ICSME 2026 Industry Track  
**Research Focus**: Newcomer onboarding patterns and community practices supporting contributor participation

## Quick Start

### Requirements

- Python 3.8+
- GitHub API token (for data collection)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd last_chance
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure GitHub token** (required for script 10):
   ```bash
   # Create a .env file
   echo "GITHUB_TOKEN=your_github_token_here" > .env
   ```
   
   To generate a GitHub token:
   - Go to https://github.com/settings/tokens
   - Create a new token with `repo` scope
   - Copy and paste it in `.env`

### Running the Pipeline

Execute all data processing scripts in the correct order:

```bash
python scripts/run_all.py
```

This runs 12 sequential scripts that:
1. Download ROS index data
2. Build package-to-repo mappings from rosdistro
3. Join index with rosdistro data
4. Validate data and generate statistics
5. Build final package dataset
6. Fill missing repository info from index.ros.org
7. Generate diagnostic reports
8. Build dataset
9. Extract unique repositories
10. Calculate repo overlap statistics
11. Extract repository features and commit history
12. Build final repository dataset

**Execution time**: ~30-60 minutes (depending on GitHub API rate limits)

### Running Individual Scripts

Each script can be run independently (if dependencies are satisfied):

```bash
python scripts/00_download_ros_index_json.py
python scripts/01_build_mapping_from_rosdistro.py
# ... etc
```

## Output Files

### Final Deliverables

- **`out/final_repo_dataset.csv`** - Main analysis dataset with repository metrics
  - Columns: Name, Owner, Description, GitHub URL, Repository Size, Stars, Forks, Issues, Topics, License, Community indicators, Commit count, Contributors, Languages, ROS distributions

- **`out/diagnostics/`** - Diagnostic reports
  - `resolved_ok.csv` - Successfully resolved packages
  - `missing_repo_key__not_in_rosdistro_release.csv` - Packages not in rosdistro
  - `repo_key_but_no_url_in_rosdistro.csv` - Packages with missing URLs
  - `non_github_url.csv` - Non-GitHub repositories

- **`out/final/`** - Per-distribution package datasets
  - `final_humble_packages_to_github.csv`
  - `final_jazzy_packages_to_github.csv`
  - `final_kilted_packages_to_github.csv`

### Generated Data

- **`data/ros_robotics_data/<owner>__<repo>/`** - Per-repository snapshots
  - `general_info.json` - Repository metadata
  - `commits.json` - Commit history (simplified)
  - `contributors.json` - List of contributors
  - `pull_requests.json` - PR metadata
  - `issues.json` - Issue metadata
  - `stars.json` - Star history with dates
  - `forks.json` - Fork information
  - `languages.json` - Programming languages used
  - `license.json` - License information
  - `readme.json` - README file location
  - `contributing.json` - CONTRIBUTING file location
  - `code_of_conduct.json` - CODE_OF_CONDUCT file location
  - `issue_template.json` - Issue template presence
  - `pr_template.json` - PR template presence
  - `weekly_commit_activity.json` - Weekly commit statistics

## Data Sources

- **ROS Index**: https://index.ros.org/ (via https://index.ros.org/search/packages/data.{distro}.json)
- **ROSDisto**: https://github.com/ros/rosdistro (YAML distribution files)
- **GitHub API**: Repository metadata, commits, contributors, PRs, issues

## Project Structure

```
last_chance/
├── scripts/                      # Data processing pipeline
│   ├── 00_download_ros_index_json.py
│   ├── 01_build_mapping_from_rosdistro.py
│   ├── 02_join_index_with_rosdistro.py
│   ├── 03_validate_and_stats.py
│   ├── 04_build_final_dataset.py
│   ├── 05_fill_missing_from_index_html.py
│   ├── 06_diagnose_unresolved.py
│   ├── 07_build_paper_proof_dataset.py
│   ├── 08_extract_unique_repos.py
│   ├── 09_repo_overlap_table.py
│   ├── 10_extract_repo_features_and_commits.py
│   ├── 11_build_final_repo_dataset.py
│   └── run_all.py               # Master runner script
├── cache/                        # Downloaded ROS index/rosdistro (generated)
├── data/                         # Repository snapshots (generated)
├── out/                          # Final outputs (generated)
├── requirements.txt              # Python dependencies
├── .env                          # GitHub token (local, not in repo)
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```
