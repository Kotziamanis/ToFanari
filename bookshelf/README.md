# ToFanari Bookshelf — Static Web

Static bookshelf system for Bunny.net hosting, linked from Thinkific lessons.

## Deployment to Bunny.net

1. Upload the entire `bookshelf` folder to your Bunny.net storage zone.
2. Set up a pull zone pointing to the folder root.
3. Access via: `https://yourzone.b-cdn.net/` (or your CDN path).

## Structure

- `index.html` — Main landing page (6 category cards)
- `categories/*.html` — Category pages with book covers
- `assets/css/style.css` — Styles
- `assets/js/books-data.js` — Book data (edit to add books)
- `assets/js/render-books.js` — Renders bookshelf from data
- `assets/images/` — Cover images (replace placeholder.svg with real covers)

## Adding Books

Edit `assets/js/books-data.js` and add entries to the appropriate category:

```javascript
{ id: "unique-id", title: "Βook Title", subtitle: "Subtitle", cover: "assets/images/cover.jpg", flipbookUrl: "https://..." }
```

Replace `flipbookUrl` with your actual FlipBuilder / Flipbook URLs.
