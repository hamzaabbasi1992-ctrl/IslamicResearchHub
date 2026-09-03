// Client-Side Logic with Live Settings, Advanced Highlighting, Multi-Filters & Sorting
let allWaqiat = [];
let filteredWaqiat = [];
let currentPage = 1;
const itemsPerPage = 24;
let favorites = JSON.parse(localStorage.getItem('waqiat_favs') || '[]');
let activeView = 'all';

// DOM Elements
const storiesGrid = document.getElementById('stories-grid');
const storiesScrollContainer = document.getElementById('stories-scroll-container');
const searchInput = document.getElementById('search-input');
const clearSearchBtn = document.getElementById('clear-search');
const sortOrderSelect = document.getElementById('sort-order-select');
const searchModeSelect = document.getElementById('search-mode-select');
const bookFilter = document.getElementById('book-filter');
const personalityFilter = document.getElementById('personality-filter');
const subjectFilter = document.getElementById('subject-filter');
const lengthFilter = document.getElementById('length-filter');

const resultsCount = document.getElementById('results-count');
const statTotal = document.getElementById('stat-total');
const statBooks = document.getElementById('stat-books');
const favCountSpan = document.getElementById('fav-count');
const navTotalCount = document.getElementById('nav-total-count');
const loadMoreBtn = document.getElementById('load-more-btn');
const navAllBtn = document.getElementById('nav-all');
const navFavsBtn = document.getElementById('nav-favs');
const toastEl = document.getElementById('toast');

// Settings Controls
const fontStyleSelect = document.getElementById('font-style-select');
const fontSizeSelect = document.getElementById('font-size-select');
const fontWeightSelect = document.getElementById('font-weight-select');
const bgColorSelect = document.getElementById('bg-color-select');

// Scroll Buttons
const scrollToTopBtn = document.getElementById('scroll-to-top');
const scrollToBottomBtn = document.getElementById('scroll-to-bottom');

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

        const totalFormatted = allWaqiat.length.toLocaleString('ur-PK');
        statTotal.textContent = totalFormatted;
        if (navTotalCount) navTotalCount.textContent = totalFormatted;

        const booksSet = new Set(allWaqiat.map(w => w.book_title).filter(Boolean));
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

    const personsSet = new Set();
    allWaqiat.forEach(w => {
        if (w.key_figures && Array.isArray(w.key_figures)) {
            w.key_figures.forEach(p => { if (p && p.trim()) personsSet.add(p.trim()); });
        }
    });
    Array.from(personsSet).sort().forEach(person => {
        const opt = document.createElement('option');
        opt.value = person;
        opt.textContent = person;
        personalityFilter.appendChild(opt);
    });

    const subjectsSet = new Set(allWaqiat.map(w => w.subject).filter(Boolean));
    Array.from(subjectsSet).sort().forEach(subj => {
        const opt = document.createElement('option');
        opt.value = subj;
        opt.textContent = subj;
        subjectFilter.appendChild(opt);
    });
}

// Tokenize query into clean words
function getSearchTokens(query, mode) {
    if (!query) return [];
    if (mode === 'exact') return [query.trim()];
    return query.split(/\s+/).map(t => t.trim()).filter(t => t.length > 0);
}

// 🌟 HIGHLIGHT FUNCTION: Wraps matching keywords with <mark class="highlight-term">
function highlightText(text, tokens) {
    if (!text || !tokens || tokens.length === 0) return escapeHtml(text);
    
    let escaped = escapeHtml(text);
    // Sort tokens by length descending so longer words match first
    const sortedTokens = [...tokens].sort((a, b) => b.length - a.length);

    sortedTokens.forEach(token => {
        if (!token) return;
        const escToken = token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        // Regex with unicode case insensitivity
        const regex = new RegExp(`(${escToken})`, 'gi');
        escaped = escaped.replace(regex, '<mark class="highlight-term">$1</mark>');
    });

    return escaped;
}

// Apply Filters & Search
function applyFilters() {
    const query = searchInput.value.trim();
    const queryLower = query.toLowerCase();
    const mode = searchModeSelect.value;
    const tokens = getSearchTokens(queryLower, mode);

    const selectedBook = bookFilter.value;
    const selectedPersonality = personalityFilter.value;
    const selectedSubject = subjectFilter.value;
    const selectedLength = lengthFilter.value;
    const sortOrder = sortOrderSelect.value;

    let baseList = (activeView === 'favs') 
        ? allWaqiat.filter(w => favorites.includes(w.id))
        : allWaqiat;

    filteredWaqiat = baseList.filter(w => {
        // Search Matching
        let matchesQuery = true;
        if (tokens.length > 0) {
            const searchableText = `${w.title || ''} ${w.text || ''} ${w.book_title || ''} ${(w.key_figures || []).join(' ')} ${w.citation || ''}`.toLowerCase();
            
            if (mode === 'exact') {
                matchesQuery = searchableText.includes(tokens[0]);
            } else if (mode === 'any') {
                matchesQuery = tokens.some(t => searchableText.includes(t));
            } else { // 'all' (default)
                matchesQuery = tokens.every(t => searchableText.includes(t));
            }
        }

        // Book Filter
        const matchesBook = !selectedBook || w.book_title === selectedBook || (w.book_title && w.book_title.includes(selectedBook));

        // Personality Filter
        const matchesPersonality = !selectedPersonality || 
            (w.key_figures && w.key_figures.some(f => f.includes(selectedPersonality))) ||
            (w.text && w.text.includes(selectedPersonality));

        // Subject Filter
        const matchesSubject = !selectedSubject || w.subject === selectedSubject;

        // Length Filter
        let matchesLength = true;
        const wordCount = (w.text || '').split(/\s+/).length;
        if (selectedLength === 'short') matchesLength = wordCount < 200;
        else if (selectedLength === 'medium') matchesLength = wordCount >= 200 && wordCount <= 500;
        else if (selectedLength === 'long') matchesLength = wordCount > 500;

        return matchesQuery && matchesBook && matchesPersonality && matchesSubject && matchesLength;
    });

    // Sorting
    sortResults(filteredWaqiat, sortOrder, tokens);

    currentPage = 1;
    resultsCount.textContent = `${filteredWaqiat.length.toLocaleString('ur-PK')} واقعات ملے۔`;
    renderGrid();
}

function sortResults(list, sortOrder, tokens) {
    if (sortOrder === 'relevance' && tokens.length > 0) {
        list.sort((a, b) => {
            const scoreA = calculateRelevance(a, tokens);
            const scoreB = calculateRelevance(b, tokens);
            return scoreB - scoreA;
        });
    } else if (sortOrder === 'longest') {
        list.sort((a, b) => (b.text || '').length - (a.text || '').length);
    } else if (sortOrder === 'shortest') {
        list.sort((a, b) => (a.text || '').length - (b.text || '').length);
    } else if (sortOrder === 'title_asc') {
        list.sort((a, b) => (a.title || '').localeCompare(b.title || '', 'ur'));
    } else { // 'book_order' or default
        list.sort((a, b) => (a.book_id || 0) - (b.book_id || 0) || (a.id || 0) - (b.id || 0));
    }
}

function calculateRelevance(item, tokens) {
    let score = 0;
    const titleLower = (item.title || '').toLowerCase();
    const textLower = (item.text || '').toLowerCase();

    tokens.forEach(t => {
        if (titleLower.includes(t)) score += 15;
        const occurrences = (textLower.match(new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length;
        score += occurrences * 2;
    });
    return score;
}

// Render Stories Grid
function renderGrid() {
    storiesGrid.innerHTML = '';
    const visibleItems = filteredWaqiat.slice(0, currentPage * itemsPerPage);
    const query = searchInput.value.trim().toLowerCase();
    const mode = searchModeSelect.value;
    const tokens = getSearchTokens(query, mode);

    if (visibleItems.length === 0) {
        storiesGrid.innerHTML = `
            <div class="loading-spinner">
                <p>کوئی واقعہ نہیں ملا۔ لطفاً سرچ کا معیار یا فلٹر تبدیل کریں۔</p>
            </div>
        `;
        loadMoreBtn.style.display = 'none';
        return;
    }

    visibleItems.forEach((w, index) => {
        const card = document.createElement('div');
        card.className = 'story-card';
        card.id = `story-card-${w.id || index}`;
        const isFav = favorites.includes(w.id);

        let figsBadge = (w.key_figures && w.key_figures.length) 
            ? `<span class="tag figure-tag">👤 ${highlightText(w.key_figures.join(', '), tokens)}</span>` 
            : '';

        const highlightedTitle = highlightText(w.title, tokens);
        const highlightedBody = highlightText(w.text, tokens);
        const highlightedBook = highlightText(w.book_title, tokens);
        const highlightedSubject = highlightText(w.subject, tokens);
        const highlightedCitation = highlightText(w.citation, tokens);

        card.innerHTML = `
            <div class="story-header">
                <div class="story-title">✦ ${highlightedTitle}</div>
                <button class="fav-btn ${isFav ? 'active' : ''}" onclick="toggleFav(${w.id})">
                    ${isFav ? '★' : '☆'}
                </button>
            </div>

            <div class="story-meta-tags">
                <span class="tag subject-tag">🏷️ ${highlightedSubject}</span>
                ${figsBadge}
                <span class="tag">📚 ${highlightedBook}</span>
            </div>

            <div class="story-body">${highlightedBody}</div>

            <div class="story-footer">
                <span class="citation-text">📍 ${highlightedCitation}</span>
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
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escapeJs(str) {
    if (!str) return '';
    return String(str).replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
}

// Quick Chip Buttons Handler
document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.chip-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const bookVal = btn.getAttribute('data-book');
        bookFilter.value = bookVal;
        applyFilters();
    });
});

// Scroll Top & Bottom Handlers
scrollToTopBtn.addEventListener('click', () => {
    storiesScrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
});

scrollToBottomBtn.addEventListener('click', () => {
    storiesScrollContainer.scrollTo({ top: storiesScrollContainer.scrollHeight, behavior: 'smooth' });
});

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
personalityFilter.addEventListener('change', applyFilters);
subjectFilter.addEventListener('change', applyFilters);
lengthFilter.addEventListener('change', applyFilters);
sortOrderSelect.addEventListener('change', applyFilters);
searchModeSelect.addEventListener('change', applyFilters);

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
