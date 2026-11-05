#!/usr/bin/env bash
# Publish part-way results while a long scrape is still running (called by scraper/run.py).
set -u
git config user.name "compare-cyprus-bot"
git config user.email "actions@users.noreply.github.com"
git add site/data data/raw data/*.md 2>/dev/null
git diff --cached --quiet && exit 0
git commit -q -m "Prices (part-way update: $1)"
for i in 1 2 3; do
  git pull -q --rebase -X theirs origin main && git push -q && break
  sleep 5
done
gh workflow run publish.yml --ref main || echo "could not start publish.yml"
