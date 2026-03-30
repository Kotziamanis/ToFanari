# GitHub repository name: `tofanari-suite`

**Canonical URL:** `https://github.com/Kotziamanis/tofanari-suite`

The old name **`ToFanari`** should be renamed on GitHub so the remote, docs, and bookmarks all match.  
This monorepo holds **PDF Marker**, **Synch-tool** (placeholder), and **Tofanari Main Tool** — the repo name is the suite, not one app.

---

## 1. Rename on GitHub (repository owner)

1. Open: **https://github.com/Kotziamanis/ToFanari** (or your current repo URL).
2. **Settings** → **General** → **Repository name**.
3. Set **`tofanari-suite`** → **Rename**.
4. GitHub keeps redirects from the old URL for a while; update bookmarks to the new URL.

---

## 2. Update your local clone

In **PowerShell** or **Git Bash**, inside your project folder:

```bat
git remote set-url origin https://github.com/Kotziamanis/tofanari-suite.git
git remote -v
git fetch
```

You should see `origin` pointing at `.../tofanari-suite.git` and `fetch` should succeed.

---

## 3. Rename the folder on your PC (optional)

Close Cursor/IDE, then rename the directory, for example:

- `ToFanari` → `tofanari-suite`
- `tofanari-pdf-marker` → `tofanari-suite`

Re-open the folder with **File → Open Folder**.

---

## 4. Push as usual

```bat
git push -u origin main
```

If you use another fork or username, replace `Kotziamanis/tofanari-suite` with your path.

---

## Other machines / collaborators

Anyone who clones fresh:

```bat
git clone https://github.com/Kotziamanis/tofanari-suite.git
cd tofanari-suite
```

Existing clones only need **`git remote set-url`** (step 2).
