/**
 * Renders bookshelf from BOOKS_DATA for the current category.
 * Expects: CATEGORY_KEY set before this script loads, or data-category on body.
 */
(function() {
    const categoryKey = window.CATEGORY_KEY || (document.body && document.body.dataset.category);
    if (!categoryKey || !window.BOOKS_DATA || !BOOKS_DATA[categoryKey]) return;

    const cat = BOOKS_DATA[categoryKey];
    const grid = document.getElementById('books-grid');
    if (!grid) return;

    var base = window.ASSET_BASE;
    if (base === undefined) {
        var path = (window.location.pathname || '').replace(/\\/g, '/');
        base = path.indexOf('categories') !== -1 ? '../' : '';
    }
    grid.innerHTML = cat.books.map(function(book) {
        const coverPath = book.cover ? (base + book.cover) : '';
        const coverContent = coverPath
            ? '<img src="' + escapeHtml(coverPath) + '" alt="' + escapeHtml(book.title) + '">'
            : '<span class="placeholder">' + escapeHtml(book.title) + '</span>';
        return '<a href="' + escapeHtml(book.flipbookUrl) + '" class="book-card" target="_blank" rel="noopener">' +
            '<div class="book-cover">' + coverContent + '</div>' +
            '<div class="book-info">' +
            '<h3 class="book-title">' + escapeHtml(book.title) + '</h3>' +
            (book.subtitle ? '<p class="book-subtitle">' + escapeHtml(book.subtitle) + '</p>' : '') +
            '</div></a>';
    }).join('');

    function escapeHtml(s) {
        if (!s) return '';
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }
})();
