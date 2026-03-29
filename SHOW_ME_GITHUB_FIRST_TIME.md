# Show me: put this project on GitHub (first time)

Follow these steps in order. Use **Safari** or **Chrome**.

---

## Step 1 — Log in to GitHub

1. Open **https://github.com**
2. Click **Sign in** (top right).  
   - If you have no account, click **Sign up** and create one (email + password).

---

## Step 2 — Create a new empty repository

1. While logged in, click the **+** (plus) at the **top right** of GitHub.
2. Click **New repository**.

Fill in only this:

| Field | What to type or choose |
|--------|-------------------------|
| **Repository name** | `tofanari-pdf-marker` (or any name you like) |
| **Public** or **Private** | Your choice (Public = anyone can see the code) |

**Important — leave these UNCHECKED / empty:**

- **Do not** tick “Add a README file”
- **Do not** add .gitignore
- **Do not** choose a license  

(Your Mac folder already has those files; an empty repo avoids conflicts.)

3. Click the green button **Create repository**.

---

## Step 3 — Copy your repository address

After creating, GitHub shows a page with a green box and commands.

1. Find the box that says **HTTPS**.
2. Copy the line that looks like:

   `https://github.com/YOUR_USERNAME/tofanari-pdf-marker.git`

   (`YOUR_USERNAME` will be your real GitHub username.)

Keep this copied — you need it in Step 5.

---

## Step 4 — Open Terminal on your Mac

1. Press **⌘ + Space** (Command + Space).
2. Type **Terminal** and press **Enter**.
3. In the Terminal window, paste this line and press **Enter**:

   ```bash
   cd ~/tofanari-pdf-marker
   ```

---

## Step 5 — Connect your folder to GitHub and upload

**A.** Paste this, but **replace the whole URL** with the one you copied in Step 3:

```bash
git remote add origin https://github.com/YOUR_USERNAME/tofanari-pdf-marker.git
```

Press **Enter**.

- If it says **“remote origin already exists”**, run this first, then try **A** again with the correct URL:

  ```bash
  git remote remove origin
  ```

**B.** Upload your code:

```bash
git push -u origin main
```

Press **Enter**.

---

## Step 6 — Log in when Git asks

- GitHub **no longer accepts your normal password** for this.
- When Terminal asks for **Password**, use a **Personal Access Token** instead:

  1. In the browser, open **https://github.com/settings/tokens**
  2. **Generate new token** → **Generate new token (classic)**
  3. Give it a name, turn on **repo**, click **Generate token**
  4. **Copy the token** (you only see it once)
  5. In Terminal, for **Username** type your GitHub username; for **Password**, **paste the token**

After a successful push, refresh your repository page on GitHub — you should see all your files.

---

## Easier alternative: GitHub Desktop (no Terminal token)

1. Install **GitHub Desktop**: **https://desktop.github.com**
2. Sign in to GitHub inside the app.
3. **File → Add Local Repository** → choose folder **`tofanari-pdf-marker`** (in your home folder).
4. **Repository → Repository settings → Remote** — if empty, paste your repo URL from Step 3.
5. Click **Publish repository** or **Push origin** if it already exists.

---

## After it works

- On GitHub: open **Actions** and wait for the Windows build to finish.
- On your PC: download **PDFMarkerTool** from **Artifacts** (see `HOW_TO_DOWNLOAD_WINDOWS_EXE.md`).
