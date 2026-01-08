class ArxivDownloader {
    constructor() {
        this.apiBase = window.location.origin;
        this.currentKeywords = '';
        this.init();
    }

    init() {
        this.searchBtn = document.getElementById('searchBtn');
        this.keywordsInput = document.getElementById('keywords');
        this.resultsDiv = document.getElementById('results');
        this.topPapersDiv = document.getElementById('topPapers');
        this.loadingDiv = document.getElementById('loading');
        this.errorDiv = document.getElementById('error');
        this.papersTable = document.querySelector('#papersTable tbody');
        this.totalPapersSpan = document.getElementById('totalPapers');

        this.searchBtn.addEventListener('click', () => this.searchPapers());
        this.keywordsInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.searchPapers();
        });

        // Load keywords from URL if present
        const urlParams = new URLSearchParams(window.location.search);
        const savedKeywords = urlParams.get('keywords');
        if (savedKeywords) {
            this.keywordsInput.value = savedKeywords;
            this.searchPapers(); // Auto-search on load
        }
    }

    async searchPapers() {
        const keywords = this.keywordsInput.value.trim();
        this.currentKeywords = keywords;
        
        if (!keywords) {
            this.showError('Please enter keywords');
            return;
        }

        this.showLoading();
        try {
            const response = await fetch(`${this.apiBase}/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({ keywords })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `API Error: ${response.status}`);
            }

            const data = await response.json();
            this.displayResults(data);
        } catch (error) {
            console.error('Search error:', error);
            this.showError(`Search failed: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    displayResults(data) {
        // Show top 5 papers prominently
        this.displayTopPapers(data.top_papers);
        
        // Show all results
        this.resultsDiv.classList.remove('hidden');
        this.totalPapersSpan.textContent = `${data.total}`;
        this.papersTable.innerHTML = '';

        data.papers.forEach(paper => {
            const row = this.createPaperRow(paper);
            this.papersTable.appendChild(row);
        });
    }

    displayTopPapers(topPapers) {
        this.topPapersDiv.innerHTML = '';
        if (topPapers.length === 0) return;

        const title = document.createElement('h3');
        title.innerHTML = '<i class="fas fa-star"></i> Top 5 Most Relevant Papers';
        title.style.cssText = 'color: #28a745; margin: 20px 0 10px 0; font-size: 1.3em; font-weight: bold;';
        this.topPapersDiv.appendChild(title);

        const topContainer = document.createElement('div');
        topContainer.style.cssText = 'display: flex; flex-wrap: wrap; gap: 15px; margin-bottom: 20px;';

        topPapers.forEach(paper => {
            const card = this.createTopPaperCard(paper);
            topContainer.appendChild(card);
        });

        this.topPapersDiv.appendChild(topContainer);
        this.topPapersDiv.classList.remove('hidden');
    }

    createTopPaperCard(paper) {
        const encodedKeywords = encodeURIComponent(this.currentKeywords);
        const card = document.createElement('div');
        card.style.cssText = `
            flex: 1 1 300px; background: linear-gradient(135deg, #1f2933, #764ba2 100%);
            color: white; padding: 20px; border-radius: 15px; cursor: pointer;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
            transition: all 0.3s ease; min-height: 200px; display: flex; flex-direction: column;
        `;
        card.onclick = () => window.location.href = `/paper/${paper.id}?keywords=${encodedKeywords}`;

        card.innerHTML = `
            <div style="font-weight: bold; font-size: 1.1em; margin-bottom: 10px; line-height: 1.3;">
                ${paper.title.length > 80 ? paper.title.substring(0, 80) + '...' : paper.title}
            </div>
            <div style="font-size: 0.9em; opacity: 0.9; margin-bottom: 10px;">
                ${paper.authors.slice(0, 2).join(', ')}${paper.authors.length > 2 ? ' et al.' : ''}
            </div>
            <div style="font-size: 0.85em; opacity: 0.8; margin-bottom: 10px; flex-grow: 1;">
                ${paper.summary}
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.9em;">
                <span>📅 ${paper.published}</span>
                <div style="background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 20px; font-weight: bold;">
                    ⭐ ${paper.relevance_score.toFixed(3)}
                </div>
            </div>
        `;
        return card;
    }

    createPaperRow(paper) {
        const encodedKeywords = encodeURIComponent(this.currentKeywords);
        const row = document.createElement('tr');
        
        const relevanceClass = paper.is_top ? 'top-paper' : '';
        const relevanceBadge = paper.is_top ? '⭐ TOP' : '';
        
        row.className = relevanceClass;
        row.innerHTML = `
            <td>${paper.id}</td>
            <td class="title-cell ${relevanceClass}" 
                title="${paper.title}" 
                style="cursor: pointer; color: ${paper.is_top ? '#28a745' : '#4facfe'}; 
                       text-decoration: ${paper.is_top ? 'underline' : 'none'}; font-weight: ${paper.is_top ? 'bold' : '500'};"
                onclick="window.location.href='/paper/${paper.id}?keywords=${encodedKeywords}'">
                ${paper.title} ${relevanceBadge ? `<span style="font-size: 0.8em; color: #ffd700;">(${relevanceBadge})</span>` : ''}
            </td>
            <td>${paper.published}</td>
            <td>${paper.authors.slice(0, 2).join(', ')}${paper.authors.length > 2 ? ' et al.' : ''}</td>
            <td>
                <button class="download-btn" onclick="downloader.downloadPaper(${paper.id}, '${this.currentKeywords}')">
                    <i class="fas fa-download"></i> Download
                </button>
            </td>
        `;
        return row;
    }

    async downloadPaper(paperId, keywords) {
        try {
            const response = await fetch(`${this.apiBase}/download/${paperId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({ keywords })
            });

            const data = await response.json();
            if (response.ok) {
                const link = document.createElement('a');
                link.href = `${this.apiBase}${data.path}`;
                link.download = data.filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } else {
                throw new Error(data.detail || 'Download failed');
            }
        } catch (error) {
            this.showError(`Download failed: ${error.message}`);
        }
    }

    showLoading() {
        this.loadingDiv.classList.remove('hidden');
        this.resultsDiv.classList.add('hidden');
        this.topPapersDiv.classList.add('hidden');
        this.errorDiv.classList.add('hidden');
    }

    hideLoading() {
        this.loadingDiv.classList.add('hidden');
    }

    showError(message) {
        this.errorDiv.textContent = message;
        this.errorDiv.classList.remove('hidden');
    }
}

// Initialize app
const downloader = new ArxivDownloader();
