# SmartTube Setup: Google Login & Best Settings / SmartTube 设置：Google 登录与推荐设置

The X50 IHU runs Android 5, so the **Google Play Store and the official YouTube app cannot be installed**. Google Play Services no longer supports Android 5 and needs root/system access, and the current YouTube app needs Android 8 or newer.
X50 IHU 是 Android 5，所以**无法安装 Google Play Store 和官方 YouTube App**（Google Play Services 已不支持 Android 5，而且需要 Root / System 权限，最新 YouTube 需要 Android 8 以上）。

**SmartTube** is the best replacement. It works without Google Play Services and **lets you log in to your own Google account** to get your subscriptions, history and playlists, with no ads.
**SmartTube** 是最好的替代方案：不需要 Google Play Services，**可以登录自己的 Google 账号**（订阅、观看记录、播放列表都在），而且没有广告。

> ⚠️ For safety, only watch videos while parked. Use audio-only / background play while driving.
> ⚠️ 为了安全，只在停车时看视频。开车时请使用纯音频 / 后台播放。

---

## Step 1 — Install SmartTube / 步骤 1 — 安装 SmartTube

Follow the **SmartTube 32.56** installer steps in the [README notices](README.md). Remove the old version with the uninstall script first (V1, then V2 if needed).
按照 [README](README.md) 里 **SmartTube 32.56** 的安装步骤。先用 Uninstall Script（V1，不行再用 V2）删除旧版本。

---

## Step 2 — Log in to Google / 步骤 2 — 登录 Google 账号

You do **not** type your password on the car screen. You approve the login on your phone.
**不需要**在车上输入密码，用手机确认登录就可以。

1. Make sure the IHU has internet (phone hotspot or Wi-Fi).
   确认 IHU 有网络（手机 Hotspot 或 Wi-Fi）。
2. Open SmartTube → **Settings (⚙️) → Accounts → Add account**.
   打开 SmartTube → **Settings (⚙️) → Accounts → Add account**。
3. SmartTube shows a **code** (for example `ABC-DEF-GHI`).
   SmartTube 会显示一组 **Code**（例如 `ABC-DEF-GHI`）。
4. On your phone, open **https://yt.be/activate** (same as `youtube.com/activate`), sign in with your Google account and enter the code.
   用手机打开 **https://yt.be/activate**（即 `youtube.com/activate`），登录 Google 账号，然后输入 Code。
5. Choose your account / channel and tap **Allow**. Within a few seconds SmartTube shows your subscriptions.
   选择账号 / 频道，按 **Allow**。几秒钟后 SmartTube 就会显示你的订阅。

If the code expires, go back and press **Add account** again to get a new code.
如果 Code 过期，重新按 **Add account** 拿新的 Code。

To log out, go to **Settings → Accounts**, select the account and remove it. You can also remove access from your Google account under *Security → Third-party connections*.
要登出：**Settings → Accounts** 选择账号删除。也可以在 Google 账号的 *Security → Third-party connections* 移除权限。

---

## Step 3 — Recommended Settings for X50 / 步骤 3 — X50 推荐设置

The X50 IHU is slow, so these settings make SmartTube smoother. Menu names may differ slightly between versions.
X50 IHU 比较慢，以下设置会让 SmartTube 更顺。不同版本的菜单名称可能有点不同。

| Setting / 设置 | Recommended / 建议 | Why / 原因 |
|---|---|---|
| Player → Video quality / 画质 | **720p** (or 480p on a slow hotspot) | Less lag and less mobile data / 比较不卡，也省流量 |
| Player → Video buffer | **Low** | Uses less memory / 少用内存 |
| Player → Background playback / 后台播放 | **On (audio only or PIP)** | Keep listening when you switch to other apps / 切换 App 时继续播放声音 |
| SponsorBlock | **On** | Skips sponsor segments automatically / 自动跳过赞助片段 |
| Interface → UI scale | Increase if text is too small / 字太小就调大 | Easier to tap while parked / 停车时更容易按 |
| Updates → Auto check | **Off** | Update with the USB installer instead; in-app updates may not install correctly on the IHU / 用 USB Installer 更新，App 内更新在 IHU 可能装不好 |

Also block SmartTube notifications:
同时 Block SmartTube 的通知：

**Hidden Settings → Sounds & Notification → App Notification → SmartTube → BLOCK**

---

## Saving Mobile Data / 节省流量

- 720p uses roughly 1 GB per hour, 480p about 0.5 GB per hour, and audio-only much less.
  720p 大约每小时 1 GB，480p 大约 0.5 GB，纯音频少很多。
- For music while driving, Spotify (already in the main installer) uses much less data than video.
  开车听歌的话，Spotify（主 Installer 已包含）比看视频省很多流量。

---

## Troubleshooting / 常见问题

| Problem / 问题 | Fix / 解决方法 |
|---|---|
| Code page doesn't load / Code 页面打不开 | Check the IHU's internet and the date/time in Settings; a wrong clock breaks login / 检查网络，以及 Settings 的日期时间（时间不对会登录失败） |
| "Video unavailable" or videos won't play / 视频无法播放 | YouTube changes often; install the latest SmartTube with the installer / YouTube 常常改，用 Installer 装最新版 SmartTube |
| Very laggy / 很卡 | Lower quality to 480p, close other apps, see [Optimization.md](Optimization.md) / 画质调到 480p，关掉其他 App，参考 [Optimization.md](Optimization.md) |
| Logged out after update / 更新后被登出 | Log in again with Step 2 / 按步骤 2 重新登录 |
