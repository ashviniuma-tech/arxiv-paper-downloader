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
        this.resultsDiv.classList.remove('hidden');
        this.totalPapersSpan.textContent = `${data.total}`;
        this.papersTable.innerHTML = '';

        data.papers.forEach(paper => {
            const row = this.createPaperRow(paper);
            this.papersTable.appendChild(row);
        });
    }

    createPaperRow(paper) {
        const encodedKeywords = encodeURIComponent(this.currentKeywords);
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${paper.id}</td>
            <td class="title-cell" 
                title="${paper.title}" 
                style="cursor: pointer; color: #4facfe; text-decoration: underline; font-weight: 500;"
                onclick="window.location.href='/paper/${paper.id}?keywords=${encodedKeywords}'">
                ${paper.title}
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
