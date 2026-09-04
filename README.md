# Web Designs Online YouTube Automation

A configurable Python pipeline for producing practical web-design videos for [Web Designs Online](https://www.youtube.com/@Web-Designs-Online). It uses Gemini for topic/script generation, gTTS for narration, Pexels for visuals, MoviePy/FFmpeg for rendering, and the YouTube Data API for uploads.

## Safe rollout

Use this order: **dry run → local private upload → GitHub Actions private upload → unlisted → public**. The default privacy mode is private. The system does not promise views, subscribers, revenue, or monetization.

## Architecture

- `config/`: channel, pillars, CTA and video style settings.
- `src/repository.py`: atomic JSON persistence, backups and legacy migration.
- `src/topic_engine.py`: niche topics, deterministic scoring, deduplication and queue replenishment.
- `src/generator.py`: Gemini, Pexels, narration and video rendering.
- `src/quality.py`: script quality firewall.
- `src/uploader.py`: OAuth upload with configurable category and privacy.
- `src/analytics.py`: non-blocking analytics snapshots and winner review.
- `data/`: runtime topics, videos, analytics, experiments and immutable history.
- `.github/workflows/main.yml`: scheduled automation.

## Prerequisites

Python 3.11, FFmpeg, ImageMagick, a Google AI Studio API key, a Pexels key, and a YouTube OAuth client configured for the YouTube Data API v3.

```bash
pip install -r requirements.txt
python main.py --dry-run
python main.py --generate-topic
python main.py --full
```

`--full` is the only command that renders and uploads. Uploads default to private. Set `YOUTUBE_PRIVACY_STATUS=unlisted` or `public` only after reviewing output.

## Google and YouTube authorization

1. Create/select a Google Cloud project.
2. Enable YouTube Data API v3.
3. Configure an OAuth consent screen and add your Google account as a test user if required.
4. Create a Desktop OAuth client and download it as `client_secrets.json`.
5. Run `python main.py --full` locally once. Approve access in the browser; this creates `credentials.json`.
6. Base64 encode both JSON files without committing them:

```bash
base64 -w 0 client_secrets.json > encoded_client_secret.txt
base64 -w 0 credentials.json > encoded_credentials.txt
```

## GitHub Actions

Add these repository Actions secrets: `GOOGLE_API_KEY`, `PEXELS_API_KEY`, `CLIENT_SECRET_B64`, and `CREDENTIALS_B64`. Run the workflow manually first. Inspect artifacts and confirm the YouTube video is private. The daily schedule is near 07:00 UTC and uses serialized concurrency.

The workflow must have permission to commit generated JSON state. Never print secrets or commit OAuth files. Adjust the channel, CTA, pillars, and publishing mode in `config/` rather than editing Python source.

## CLI

```bash
python main.py --dry-run
python main.py --generate-topic
python main.py --generate-script TOPIC_ID
python main.py --render TOPIC_ID
python main.py --upload TOPIC_ID
python main.py --analytics
python main.py --learn
python main.py --full
```

Stage-specific commands are safe planning entry points; use `--full` for the complete render/upload path. Existing `content_plan.json` is migrated into `data/topics.json` on first run.

## Content strategy

The configured pillars cover landing pages, UI/UX, responsive design, HTML/CSS, JavaScript, WordPress, Webflow, Framer, Shopify, accessibility, SEO, performance, CRO, AI-assisted creation, freelancing and agency systems. The queue replenishes before it empties and rejects near-duplicate titles.

## Troubleshooting

- Missing `GOOGLE_API_KEY`: configure it locally or as an Actions secret.
- Missing OAuth files: complete the authorization steps above.
- FFmpeg/ImageMagick errors: install both binaries and verify they are on `PATH`.
- Empty Pexels results: the renderer intentionally falls back to a solid background.
- Upload failures: the topic remains incomplete; rerun after fixing credentials.
- Analytics failures do not block production.

## Security and limitations

Secrets remain outside source control. JSON is suitable for a single serialized GitHub Actions worker; move to a database adapter for concurrent multi-worker production. Generated content still requires human review for factual accuracy, accessibility, copyright and platform-policy compliance.

## License

MIT License.
