import os
import csv
from collections import defaultdict

IN_OK = "out/diagnostics/resolved_ok.csv"
OUT_DIR = "out/final"
os.makedirs(OUT_DIR, exist_ok=True)

def main():
    with open(IN_OK, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rows = [r for r in rows if (r.get("github_owner") and r.get("github_repo"))]

    by_distro = defaultdict(list)
    for r in rows:
        by_distro[r["ros_distro"]].append(r)

    for d, rs in by_distro.items():
        out_path = os.path.join(OUT_DIR, f"final_{d}_packages_to_github.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rs[0].keys()))
            w.writeheader()
            w.writerows(rs)
        print(f"[OK] saved {out_path} rows={len(rs)}")

    all_path = os.path.join(OUT_DIR, "final_all_distros_packages_to_github.csv")
    with open(all_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[OK] saved {all_path} rows={len(rows)}")

if __name__ == "__main__":
    main()
