# GrabNest - Setup (Hinglish)

- `docs/index.html` -> website (GitHub Pages)
- `backend/`        -> Python + yt-dlp server (koi RapidAPI / limit nahi)

GitHub Pages par Python nahi chalta, isliye backend alag server par lagta hai.

## Step 1: GitHub
Naya repo banao aur zip ka poora content upload karo.

## Step 2: Backend deploy (Render, Docker)
1. render.com > New > Blueprint > apna repo chuno (`render.yaml` Docker se ffmpeg bhi install kar dega).
   Ya New > Web Service > Runtime: Docker, Root/Context: `backend`.
2. Environment variable: `ALLOWED_ORIGIN` = `https://TUMHARA-USERNAME.github.io`
3. Deploy ke baad URL kholo: `{"ok":true,...}` dikhna chahiye.

## Step 3: Website ko jodo
`docs/index.html` mein `API_BASE` mein apna Render URL daalo (aakhir mein `/` nahi). Commit karo.

## Step 4: GitHub Pages
Repo > Settings > Pages > Branch `main`, folder `/docs` > Save.

## Zaroori baatein
- YouTube aksar free/datacenter servers ko block kar deta hai ("Sign in to confirm you're not a bot"). Fix: browser mein YouTube login karke
  "Get cookies.txt LOCALLY" extension se cookies.txt export karo, use base64 karo aur Render env `COOKIES_B64` mein daalo.
  Phir bhi na chale to VPS (jaise ~$5 mahina) ya ghar ka PC use karo.
- Instagram/Facebook ke private ya login wale video ke liye bhi cookies chahiye.
- yt-dlp ko update rakho: Render mein "Clear build cache & deploy" karte raho (har kuch hafte).
- Render free plan 15 min idle par so jata hai (pehla check 30-60 sec) aur bade video ke liye kam padta hai.
- Server ek saath 2 download karta hai aur ek IP ko 1 min mein 15 requests deta hai (`MAX_JOBS`, `MAX_MINUTES` badal sakte ho).
- Ads: download dabane par tumhara smartlink naye tab mein khulta hai aur popup ad aata hai. Ads khud click nahi karwaye jate.
- Sirf wahi content download karo jiska tumhe haq ya permission ho.
