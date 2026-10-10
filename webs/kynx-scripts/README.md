# kynx-scripts: save and open code on Cloudflare

Write code in the browser, save it, open it later by ID or share link. Scripts are only stored, never run.

## Deploy
```
npm install
npx wrangler kv namespace create SCRIPTS     # copy the printed id into wrangler.toml
npx wrangler deploy
```
Open the printed `https://kynx-scripts.<you>.workers.dev` URL.

## Use
- **Save**: new script, gives an ID and a share link (`/#ID`) plus a raw link (`/raw/ID`).
- **Open**: type an ID, or open a share link.
- **Update / Delete**: only from the browser that saved it (a secret token is kept in that browser's localStorage; the server stores only its hash).
- Limit: 256 KB per script. Anyone with an ID can read it, so don't store secrets.
- Run locally: `npx wrangler dev`. Tests: `npm test`.
