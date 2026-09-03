// Client-Side Logic with Live Settings Customization
let allWaqiat = [];
let filteredWaqiat = [];
let currentPage = 1;
const itemsPerPage = 20;
let favorites = JSON.parse(localStorage.getItem('waqiat_favs') || '[]');
let activeView = 'all';

// DOM Elements
const storiesGrid = document.getElementById('stories-grid');
const searchInput = document.getElementById('search-input');
const clearSearchBtn = document.getElementById('clear-search');
const bookFilter = document.getElementById('book-filter');
const subjectFilter = document.getElementById('subject-filter');
const resultsCount = document.getElementById('results-count');
const statTotal = document.getElementById('stat-total');
const statBooks = document.getElementById('stat-books');
const favCountSpan = document.getElementById('fav-count');
const loadMoreBtn = document.getElementById('load-more-btn');
const navAllBtn = document.getElementById('nav-all');
const navFavsBtn = document.getElementById('nav-favs');
const toastEl = document.getElementById('toast');

// Settings Controls
const fontStyleSelect = document.getElementById('font-style-select');
const fontSizeSelect = document.getElementById('font-size-select');
const fontWeightSelect = document.getElementById('font-weight-select');
const bgColorSelect = document.getElementById('bg-color-select');

// Load Data directly from window.WAQIAT_DATABASE or fallback fetch
async function loadData() {
    try {
        if (window.WAQIAT_DATABASE && Array.isArray(window.WAQIAT_DATABASE)) {
            allWaqiat = window.WAQIAT_DATABASE;
        } else {
            let response = await fetch('waqiat_database.json');
            if (!response.ok) {
                response = await fetch('../data/waqiat_database.json');
            }
            if (!response.ok) throw new Error('Failed to load waqiat_database.json');
            allWaqiat = await response.json();
        }

        statTotal.textContent = allWaqiat.length.toLocaleString('ur-PK');
        const booksSet = new Set(allWaqiat.map(w => w.book_title));
        statBooks.textContent = booksSet.size + '+';

        populateFilters(booksSet);
        updateFavCount();
        applySavedSettings();
        applyFilters();

    } catch (err) {
        console.error(err);
        storiesGrid.innerHTML = `
            <div class="loading-spinner">
                <p style="color:#EF4444;">⚠️ ڈیٹا بیس لوڈ کرنے میں مسئلہ پیش آیا۔ لطفاً فائل کا وجود چیک کریں۔</p>
            </div>
        `;
    }
}

// Settings Persistence & Live Handlers
function applySavedSettings() {
    const savedFont = localStorage.getItem('waqiat_font') || 'font-nastaliq';
    const savedSize = localStorage.getItem('waqiat_size') || 'size-medium';
    const savedWeight = localStorage.getItem('waqiat_weight') || 'weight-normal';
    const savedBg = localStorage.getItem('waqiat_bg') || 'bg-navy';

    fontStyleSelect.value = savedFont;
    fontSizeSelect.value = savedSize;
    fontWeightSelect.value = savedWeight;
    bgColorSelect.value = savedBg;

    updateBodyClasses(savedFont, savedSize, savedWeight, savedBg);
}

function updateBodyClasses(font, size, weight, bg) {
    document.body.className = `${font} ${size} ${weight} ${bg}`;
    localStorage.setItem('waqiat_font', font);
    localStorage.setItem('waqiat_size', size);
    localStorage.setItem('waqiat_weight', weight);
    localStorage.setItem('waqiat_bg', bg);
}

fontStyleSelect.addEventListener('change', () => {
    updateBodyClasses(fontStyleSelect.value, fontSizeSelect.value, fontWeightSelect.value, bgColorSelect.value);
});
fontSizeSelect.addEventListener('change', () => {
    updateBodyClasses(fontStyleSelect.value, fontSizeSelect.value, fontWeightSelect.value, bgColorSelect.value);
});
fontWeightSelect.addEventListener('change', () => {
    updateBodyClasses(fontStyleSelect.value, fontSizeSelect.value, fontWeightSelect.value, bgColorSelect.value);
});
bgColorSelect.addEventListener('change', () => {
    updateBodyClasses(fontStyleSelect.value, fontSizeSelect.value, fontWeightSelect.value, bgColorSelect.value);
});

// Populate Filters
function populateFilters(booksSet) {
    const sortedBooks = Array.from(booksSet).sort();
    sortedBooks.forEach(book => {
        const opt = document.createElement('option');
        opt.value = book;
        opt.textContent = book;
        bookFilter.appendChild(opt);
    });

    const subjectsSet = new Set(allWaqiat.map(w => w.subject).filter(Boolean));
    Array.from(subjectsSet).sort().forEach(subj => {
        const opt = document.createElement('option');
        opt.value = subj;
        opt.textContent = subj;
        subjectFilter.appendChild(opt);
    });
}

// Apply Filters & Search
function applyFilters() {
    const query = searchInput.value.trim().toLowerCase();
    const selectedBook = bookFilter.value;
    const selectedSubject = subjectFilter.value;

    let baseList = (activeView === 'favs') 
        ? allWaqiat.filter(w => favorites.includes(w.id))
        : allWaqiat;

    filteredWaqiat = baseList.filter(w => {
        const matchesQuery = !query || 
            w.title.toLowerCase().includes(query) || 
            w.text.toLowerCase().includes(query) ||
            w.book_title.toLowerCase().includes(query) ||
            (w.key_figures && w.key_figures.some(f => f.toLowerCase().includes(query)));

        const matchesBook = !selectedBook || w.book_title === selectedBook;
        const matchesSubject = !selectedSubject || w.subject === selectedSubject;

        return matchesQuery && matchesBook && matchesSubject;
    });

    currentPage = 1;
    resultsCount.textContent = `${filteredWaqiat.length.toLocaleString('ur-PK')} واقعات ملے۔`;
    renderGrid();
}

// Render Stories Grid
function renderGrid() {
    storiesGrid.innerHTML = '';
    const visibleItems = filteredWaqiat.slice(0, currentPage * itemsPerPage);

    if (visibleItems.length === 0) {
        storiesGrid.innerHTML = `
            <div class="loading-spinner">
                <p>کوئی واقعہ نہیں ملا۔ لطفاً سرچ کا معیار تبدیل کریں۔</p>
            </div>
        `;
        loadMoreBtn.style.display = 'none';
        return;
    }

    visibleItems.forEach(w => {
        const card = document.createElement('div');
        card.className = 'story-card';
        const isFav = favorites.includes(w.id);

        let figsBadge = (w.key_figures && w.key_figures.length) 
            ? `<span class="tag">${w.key_figures.join(', ')}</span>` 
            : '';

        card.innerHTML = `
            <div class="story-header">
                <div class="story-title">واقعہ: ${escapeHtml(w.title)}</div>
                <button class="fav-btn ${isFav ? 'active' : ''}" onclick="toggleFav(${w.id})">
                    ${isFav ? '★' : '☆'}
                </button>
            </div>

            <div class="story-meta-tags">
                <span class="tag subject-tag">${escapeHtml(w.subject)}</span>
                ${figsBadge}
                <span class="tag">${escapeHtml(w.book_title)}</span>
            </div>

            <div class="story-body">${escapeHtml(w.text)}</div>

            <div class="story-footer">
                <span class="citation-text">📍 ${escapeHtml(w.citation)}</span>
                <button class="copy-btn" onclick="copyStoryText(\`${escapeJs(w.title)}\`, \`${escapeJs(w.text)}\`, \`${escapeJs(w.citation)}\`)">
                    📋 کاپی کریں
                </button>
            </div>
        `;
        storiesGrid.appendChild(card);
    });

    if (visibleItems.length < filteredWaqiat.length) {
        loadMoreBtn.style.display = 'block';
    } else {
        loadMoreBtn.style.display = 'none';
    }
}

// Favorites Toggle
function toggleFav(id) {
    if (favorites.includes(id)) {
        favorites = favorites.filter(fId => fId !== id);
    } else {
        favorites.push(id);
    }
    localStorage.setItem('waqiat_favs', JSON.stringify(favorites));
    updateFavCount();
    applyFilters();
}

function updateFavCount() {
    favCountSpan.textContent = favorites.length;
}

// Copy Story
function copyStoryText(title, text, citation) {
    const formatted = `واقعہ: ${title}\n\n${text}\n\nحوالہ: ${citation}\n(ماخذ: واقعات انسائیکلوپیڈیا - اسلامک ریسرچ ہب)`;
    navigator.clipboard.writeText(formatted).then(() => {
        showToast('واقعہ کا متن کاپی ہو گیا!');
    });
}

function showToast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    setTimeout(() => toastEl.classList.remove('show'), 2500);
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escapeJs(str) {
    if (!str) return '';
    return str.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
}

// Event Listeners
searchInput.addEventListener('input', () => {
    clearSearchBtn.style.display = searchInput.value ? 'block' : 'none';
    applyFilters();
});

clearSearchBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearSearchBtn.style.display = 'none';
    applyFilters();
});

bookFilter.addEventListener('change', applyFilters);
subjectFilter.addEventListener('change', applyFilters);

loadMoreBtn.addEventListener('click', () => {
    currentPage++;
    renderGrid();
});

navAllBtn.addEventListener('click', () => {
    activeView = 'all';
    navAllBtn.classList.add('active');
    navFavsBtn.classList.remove('active');
    applyFilters();
});

navFavsBtn.addEventListener('click', () => {
    activeView = 'favs';
    navFavsBtn.classList.add('active');
    navAllBtn.classList.remove('active');
    applyFilters();
});

// Initialize
loadData();
