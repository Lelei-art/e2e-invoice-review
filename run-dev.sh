#!/usr/bin/env bash

uv run --project backend --locked --no-sync uvicorn backend.app.main:app --reload &
(cd frontend && corepack pnpm dev) &
wait
