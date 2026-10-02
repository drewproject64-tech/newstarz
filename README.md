# newstarz Telegram Bot

Telegram bot implementing the requested start flow and per-user two-hour rotating withdrawal-photo schedule.

## Flow

1. /start sends the Starzbet image with the supplied Turkish message.
2. Immediately sends the first withdrawal image.
3. Each user then receives the next withdrawal image every 2 hours.
4. Rotation is 257,000 TL -> 320,000 TL -> 239,000 TL -> repeat.
5. Each user's rotation is tracked independently in memory.

## Configuration

Set `BOT_TOKEN`.

Optional image paths:
- `START_IMAGE` (default: `assets/start.jpg`)
- `WITHDRAWAL_IMAGE_1` (default: `assets/withdrawal_257000.jpg`)
- `WITHDRAWAL_IMAGE_2` (default: `assets/withdrawal_320000.jpg`)
- `WITHDRAWAL_IMAGE_3` (default: `assets/withdrawal_239000.jpg`)

> For production persistence across restarts, store user rotation state in a database rather than process memory.

## Deploy on Render

This repository includes a Docker worker configuration in `render.yaml`.
Set `BOT_TOKEN` in Render environment variables.
