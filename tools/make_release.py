"""Make the release zip: what a streamer needs, exactly as committed.

    python tools/make_release.py

1. the working tree must be clean: the zip is made from the last commit (git archive)
2. streamerbot/build.py runs again (safety check, compile check) and must give the committed .sb
3. the tests must pass, and CHANGELOG.md must have a section for the version in build.py
4. writes build/D2R-Level-Overlay.zip (a D2R-Level-Overlay folder inside) and prints its SHA-256

Then tag the commit (git tag -a v<version>), push the tag and attach the zip to a GitHub release
of that tag. The zip keeps the same name in every version, so the README's
releases/latest link always leads to it.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "D2R-Level-Overlay.zip"
FILES = ["overlay", "streamerbot/D2R-Level-Overlay.sb", "docs/images",
         "README.md", "README.pt-BR.md", "CHANGELOG.md", "LICENSE"]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def run(script):
    if subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT).returncode:
        raise SystemExit(f"{script} failed: no release")


def main():
    if git("status", "--porcelain"):
        raise SystemExit("commit everything first: the zip is made from the last commit")
    run("streamerbot/build.py")
    if git("status", "--porcelain"):
        raise SystemExit("streamerbot/D2R-Level-Overlay.sb was out of date: commit the rebuilt one and run again")
    run("streamerbot/tests/test_reader.py")
    version = re.search(r'^VERSION = "(.+)"', (ROOT / "streamerbot" / "build.py").read_text(encoding="utf-8"), re.M).group(1)
    if not re.search(rf"^## {re.escape(version)}\b", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M):
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    head = git("rev-parse", "HEAD").strip()
    tag = "v" + version
    if git("tag", "-l", tag).strip() and git("rev-list", "-n", "1", tag).strip() != head:
        raise SystemExit(f"{tag} already exists on another commit: raise VERSION in streamerbot/build.py")

    OUT.parent.mkdir(exist_ok=True)
    git("archive", "--format=zip", "--prefix=D2R-Level-Overlay/", "-o", str(OUT), "HEAD", *FILES)
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"\nrelease {tag} from commit {head[:7]}")
    print(f"  {OUT.relative_to(ROOT)}  {OUT.stat().st_size // 1024} KB")
    print(f"  SHA-256 {sha}")
    print(f"\nnext: git tag -a {tag} -m \"D2R Level Overlay {version}\" && git push origin {tag}")
    print("then on GitHub: Releases > Draft a new release > choose the tag > attach the zip > Publish")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
