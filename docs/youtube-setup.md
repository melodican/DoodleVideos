# Publishing to YouTube — one-time OAuth setup (~5 minutes)

The dashboard's **Publish to YouTube** button uploads your finished `video.mp4`
plus the generated title / description / tags using the YouTube Data API. You only
do this setup **once per computer**. After that, publishing is a single click.

## 1. Create a Google Cloud project + enable the API
1. Go to <https://console.cloud.google.com/> and create a new project
   (top bar → project dropdown → **New Project**). Name it e.g. `doodle-studio`.
2. With that project selected, open **APIs & Services → Library**, search for
   **YouTube Data API v3**, and click **Enable**.

## 2. Configure the OAuth consent screen
1. **APIs & Services → OAuth consent screen**.
2. User type: **External** → Create.
3. Fill in an app name (e.g. `Doodle Studio`) and your email where required. Save.
4. On **Test users**, click **+ Add users** and add the Google account that owns
   your YouTube channel (`glenkirkham@gmail.com`). Save.
   - While the app is in "Testing", only listed test users can authorize it —
     that's fine, it's just you. You do **not** need Google verification.

## 3. Create the OAuth client (Desktop app)
1. **APIs & Services → Credentials → + Create Credentials → OAuth client ID**.
2. Application type: **Desktop app**. Name it anything. Create.
   - Desktop-app clients accept any `localhost` redirect, so there's nothing else
     to configure.
3. Click **Download JSON** on the new client.
4. Save that file in the repo root as **`client_secret.json`**:

   ```
   /Users/glenkirkham/yt/client_secret.json
   ```

   (It's gitignored — it stays on your machine. You can point elsewhere with the
   `YT_CLIENT_SECRETS` env var if you prefer.)

## 4. First publish = grant access
1. Start the dashboard and open a project that has a rendered video.
2. Click **Publish to YouTube**.
3. A browser window opens asking you to choose your Google account and approve
   "Manage your YouTube videos". Because the app is in Testing you may see an
   "unverified app" notice — click **Advanced → Go to Doodle Studio (unsafe)**;
   it's your own app.
4. After you approve, the token is cached in `yt_token.json` (gitignored) and
   refreshed automatically. **You won't be asked again.**

## Notes
- New uploads default to **Unlisted** so you can review before going public.
  Switch the privacy dropdown to Public when you're ready.
- The API has a daily upload quota (a video insert costs ~1600 of the default
  10,000 units/day → roughly 6 uploads/day). Plenty for this workflow.
- To re-authorize with a different channel, delete `yt_token.json` and publish
  again.
