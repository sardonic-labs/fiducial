# Plan — Issue #19: create TEST_FUSIONEER.md

## Problem
Create TEST_FUSIONEER.md at repo root with exact content.

## Approach
Create single file.

## Files
- TEST_FUSIONEER.md

## Verify
python3 -m unittest discover -s tests -v && python3 scripts/docs_check.py
