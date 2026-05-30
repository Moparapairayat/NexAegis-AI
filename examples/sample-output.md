# Sample Output

```text
$ nax doctor
Health score: 82/100

Project Health
README              Good      README file found.
Git repository      Good      Git repository found.
Project manifest    Good      Python or Node project manifest found.
Tests               Good      Test directory or test files found.
GitHub Actions      Warning   Add CI workflow for tests and lint checks.
```

```text
$ nax run "rm -rf build" --dry-run
Command: rm -rf build
Allowed by policy: False
Requires confirmation: True
Reason: Recursive forced deletion can remove large parts of the filesystem.
```

```text
$ nax ci
Health   pass   82 >= 70
Risk     pass   medium <= medium
Security pass   100 >= 80
```
```text
$ nax risk
Risk score: 24/100
Level: LOW

Reasons                         Recommendations
2 changed file(s) in the tree.   Review and test the current diff before committing.
```
