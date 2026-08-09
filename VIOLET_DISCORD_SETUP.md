# Violet Discord Setup Guide

## What You Need

1. **A Discord Bot Token** — You'll create this in the Discord Developer Portal
2. **Your Server (Guild) ID** — To add Violet to your Discord server
3. **Channel ID** — Where Violet will listen and respond

---

## Step 1: Create a Discord Application

1. Go to https://discord.com/developers/applications
2. Click **"New Application"** (top right)
3. Name it "Violet" and click Create
4. Go to the **Bot** section (left sidebar)
5. Click **"Reset Token"** to generate a new token
   - ⚠️ **Copy and save this token now** — you only see it once!
6. Under "Privileged Gateway Intents", enable:
   - **Server Members Intent** (required)
   - **Message Content Intent** (required for Violet to read messages)

---

## Step 2: Get Your Server IDs

### Your Server (Guild) ID:
1. Open Discord → Server Settings → click your server name
2. If IDs are hidden: User Settings → Advanced → enable "Developer Mode"
3. Right-click your server name → "Copy ID"

### Your Channel ID:
1. In your server, right-click the text channel where Violet should listen
2. Click "Copy Channel ID"

---

## Step 3: Authorize the Bot

1. Go to https://discord.com/developers/applications → Your App → OAuth2 → URL Generator
2. Scopes: select `bot`
3. Bot Permissions: select (at minimum):
   - Read Messages/View Channels
   - Send Messages
   - Add Reactions
4. Copy the generated URL and open it in your browser
5. Select your server from the dropdown and click "Authorize"

---

## Step 4: Give Mike the Details

Message Mike with:

```
Violet Discord Setup:

🔑 Bot Token: [paste your token here]
🏠 Server ID: [paste your server ID]
📢 Channel ID: [paste the channel ID]
👤 Your Discord User ID: (right-click yourself → Copy ID)
```

---

## Step 5: Echo Will Connect Her

Once Mike has these details, Echo will:
- Add your token to Violet's config
- Set up the channel permissions
- Test the connection
- Violet will be live in your Discord! 🎉

---

## Quick Test

After setup, in your channel type:
```
@Violet hello
```

She should respond! If not, check that:
- Message Content Intent is enabled in Developer Portal
- Bot is in your server with permissions
- Channel allows the bot to read/write

---

## Need Help?

Ping Mike. He'll get Echo to sort it out. 🟣