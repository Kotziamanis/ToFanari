# Easy download on your PC (PDF Marker Tool)

Your **PDFs stay on the PC**. You only download **one program** (`PDFMarkerTool.exe`) from GitHub when you want the latest build.

---

## Your routine on the PC (do this every time you want the newest `.exe`)

**1.** Open your browser (Edge or Chrome).

**2.** Open this page (bookmark it — see below):

`https://github.com/Kotziamanis/tofanari-suite/actions/workflows/build-pdf-marker-windows.yml`

Save that page as a **bookmark** or **Favourite** called *PDF Marker builds* (after the project is pushed to GitHub).

**3.** You see a list of runs. Click the **top** row that has a **green check** ✓ (successful build).

**4.** Scroll to the bottom of that page to the section **Artifacts**.

**5.** Click **`PDFMarkerTool-Windows-x64`** — the browser downloads a **ZIP** file.

**6.** Open the ZIP (double-click). Copy **`PDFMarkerTool.exe`** to your **Desktop** or a folder you like.

**7.** Double-click **`PDFMarkerTool.exe`** to start the app. Use **Open PDF** and pick files from your PC drives as usual.

That’s the whole routine: **bookmark → green run → Artifacts → download ZIP → run `.exe`**.

---

## If you use “Releases” (optional, even simpler link)

If you (or someone) published a version with a tag like `pdf-marker-v1.0.0`, you can skip Actions and use:

`https://github.com/Kotziamanis/tofanari-suite/releases`

Download **`PDFMarkerTool.exe`** directly from the latest release.  
(To create a release from the Mac, see the short “Optional” section at the end.)

---

## One-time setup (on the Mac, or once ever)

1. Create a repository on GitHub and push this project (`tofanari-suite`) to the **`main`** branch.
2. Wait until **Actions** shows a **green** run for **Build PDF Marker (Windows EXE)** (about 2–3 minutes after the first push).
3. On the PC, do the **routine** above and bookmark the workflow page.

After that, you **never need the Mac** to *use* the tool on the PC — only to change code and push when you want a new build.

---

## When you get an updated version from development

1. On the Mac: save changes, `git commit`, `git push` to `main`.
2. On the PC: wait ~3 minutes, repeat the **routine** (same bookmark → latest **green** run → **Artifacts** → download → replace your old `PDFMarkerTool.exe` if you want).

---

## Optional: create a Release (one `.exe` link for the PC)

On the Mac, in the project folder:

```bash
git tag pdf-marker-v1.0.1
git push origin pdf-marker-v1.0.1
```

GitHub will create a **Release** with **`PDFMarkerTool.exe`** attached. On the PC, open the **Releases** page (link above) and download the file — no ZIP step.

---

## Troubleshooting

| Problem | What to do |
|--------|------------|
| No green check | Open the failed run; if it’s your repo, fix the error or ask for help. |
| No Artifacts section | The run must finish successfully (green). Failed runs have no EXE to download. |
| Windows warns about unknown publisher | Normal for unsigned apps → **More info** → **Run anyway** (if you trust this repo). |
