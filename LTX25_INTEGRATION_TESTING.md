# LTX-2.5 integration (Azure Foundry)

Status: **text-to-video only**. The video stage sends each scene's prompt to LTX-2.5 Fast and downloads the clip.
Keyframes are not used yet and singing scenes are not lip-synced (image-to-video and audio inputs are unverified).

## Azure setup

- Foundry resource in **Sweden Central** (the only region LTX/fal is offered in), with `Fal-LTX-2.5-Fast` deployed.
- A subscription owner must enable the `Microsoft.CognitiveServices/Fal.EnableDeploy` preview feature first.
- fal models are third-party: prompts are processed by fal.ai as well as Azure. Check with IT before using company or customer content.

## Configuration (`.env`, never committed)

```env
AZURE_FOUNDRY_RESOURCE_NAME=<resource name, the part before .services.ai.azure.com>
AZURE_FOUNDRY_API_KEY=<optional; Keys and Endpoint page of the resource>
```

Optional: `LTX_DEPLOYMENT` (default `Fal-LTX-2.5-Fast`), `LTX_RESOLUTION` (default `1080p`), `LTX_TIMEOUT` (seconds per clip, default 900).

Auth: with `AZURE_FOUNDRY_API_KEY` the app sends it as the `api-key` header (a `Bearer` key is rejected).
Without it the app uses Entra ID through `azure-identity` (`az login`, or `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_CLIENT_SECRET`).
Inside Docker there is no `az login`, so use the key or a service principal.

## How the API behaves (verified)

1. `POST /providers/falai/v1/lightricks/ltx-2.5/text-to-video/fast` with `model`, `prompt`, `duration`, `resolution`, `aspect_ratio` returns `request_id` and status URLs.
2. Poll `status_url` until `COMPLETED` (about a minute for a 6 s clip).
3. `GET response_url` returns `video.url`; download it with the same auth header (401 without).
4. Output is 25 fps; a 16:9 `1080p` request gave 1920x1080.

Not verified: image-to-video route/body, `negative_prompt`/audio inputs, 9:16 output size, durations other than 6 s.

## Try it

```bash
docker compose up -d --build        # ask first: the GPU is shared
curl -X POST http://localhost:8090/api/jobs ...   # upload a song with motion=draft
docker compose logs -f api
```

Each clip costs money per generation, so test with a short song section first. A failed call raises an error that includes the HTTP status and response text.
