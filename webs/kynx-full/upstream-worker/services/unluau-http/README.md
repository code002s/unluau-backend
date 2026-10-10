# KYNX Unluau backend

KYNX Cloudflare Workers cannot execute the .NET Unluau CLI directly. This small HTTP adapter runs Unluau and exposes `POST /decompile` for raw Luau bytecode. The KYNX Worker forwards Luau/Roblox requests here when `LUAU_BACKEND_URL` is configured.

Unluau is the dedicated Luau/Roblox decompiler and its CLI accepts a Luau bytecode file or stdin. See the upstream documentation:
https://github.com/atrexus/unluau

## Docker

```bash
docker build -t kynx-unluau ./services/unluau-http
docker run --rm -p 8788:8788 kynx-unluau
```

Then configure the KYNX Worker secret/variable:

```text
LUAU_BACKEND_URL=http://<your-unluau-host>:8788/decompile
```

Do not expose this backend publicly without authentication/rate limiting.

The adapter also accepts `.rbmx` XML bodies and attempts to extract base64 Luau bytecode embedded in model properties. For `.rbm` or unusual Roblox containers, use the extraction layer before forwarding the raw bytecode.
