@echo off
winget update
winget upgrade --all --include-unknown
pip-review --auto
