#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# Scripts to run in order
SCRIPTS = [
    "00_download_ros_index_json.py",
    "01_build_mapping_from_rosdistro.py",
    "02_join_index_with_rosdistro.py",
    "03_validate_and_stats.py",
    "05_fill_missing_from_index_html.py",
    "06_diagnose_unresolved.py",
    "04_build_final_dataset.py",
    "07_build_paper_proof_dataset.py",
    "08_extract_unique_repos.py",
    "09_repo_overlap_table.py",
    "10_extract_repo_features_and_commits.py",
    "11_build_final_repo_dataset.py",
]

def main():
    scripts = SCRIPTS
    
    print(f"Found {len(scripts)} scripts to run")
    print("=" * 60)
    
    failed = []
    successful = []
    
    for script in scripts:
        script_path = SCRIPT_DIR / script
        print(f"\n[RUN] {script}")
        print("-" * 60)
        
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=SCRIPT_DIR.parent
            )
            
            if result.returncode == 0:
                print(f"[OK] {script} completed successfully")
                successful.append(script)
            else:
                print(f"[ERROR] {script} exited with code {result.returncode}")
                failed.append((script, f"exit code {result.returncode}"))
                
        except Exception as e:
            print(f"[EXCEPTION] {script}: {e}")
            failed.append((script, str(e)))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Successful: {len(successful)}/{len(scripts)}")
    for s in successful:
        print(f"  ✓ {s}")
    
    if failed:
        print(f"\nFailed: {len(failed)}/{len(scripts)}")
        for s, reason in failed:
            print(f"  ✗ {s} ({reason})")
        sys.exit(1)
    else:
        print("\nAll scripts executed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
