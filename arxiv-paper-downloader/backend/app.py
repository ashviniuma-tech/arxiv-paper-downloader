from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import arxiv
import os
import re
import urllib.parse
from typing import List
from pydantic import BaseModel
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from collections import Counter
import string

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

app = FastAPI(title="arXiv Paper Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs('papers', exist_ok=True)
app.mount("/papers", StaticFiles(directory="papers"), name="papers")

class SearchResponse(BaseModel):
    papers: List[dict]
    top_papers: List[dict]
    total: int

def preprocess_text(text):
    """Simple text preprocessing without scikit-learn"""
    if not text:
        return ""
    # Remove punctuation and lowercase
    text = text.lower().translate(str.maketrans('', '', string.punctuation))
    # Tokenize
    tokens = nltk.word_tokenize(text)
    # Remove stopwords (basic list)
    stopwords = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 
                'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
                'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her',
                'she', 'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there',
                'their', 'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get',
                'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time', 'no',
                'just', 'him', 'know', 'take', 'people', 'into', 'year', 'your',
                'good', 'some', 'could', 'them', 'see', 'other', 'than', 'then',
                'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
                'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first',
                'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
                'give', 'day', 'most', 'us'}
    tokens = [word for word in tokens if word not in stopwords and len(word) > 2]
    return ' '.join(tokens)

def calculate_relevance_score(keywords_text, paper_text):
    """Calculate relevance score without scikit-learn using simple TF-IDF like approach"""
    keywords = preprocess_text(keywords_text).split()
    paper_tokens = preprocess_text(paper_text).split()
    
    if not keywords or not paper_tokens:
        return 0.0
    
    # Keyword frequency in paper
    keyword_freq = sum(1 for token in paper_tokens if token in keywords)
    
    # Paper length normalization
    paper_length = len(paper_tokens)
    if paper_length == 0:
        return 0.0
    
    # Simple TF-IDF approximation
    tf_score = keyword_freq / paper_length
    
    # IDF approximation (inverse frequency of keywords)
    unique_keywords_in_paper = len(set(token for token in paper_tokens if token in keywords))
    idf_score = np.log(len(keywords) / (unique_keywords_in_paper + 1))
    
    # Exact keyword matches bonus
    exact_matches = sum(1 for keyword in keywords if keyword in paper_tokens)
    match_bonus = exact_matches / len(keywords)
    
    return tf_score * idf_score * (1 + match_bonus)

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    try:
        with open("../frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="""
        <h1>Frontend not found!</h1>
        <p>Please ensure frontend/index.html exists.</p>
        """, status_code=404)

@app.get("/style.css")
async def serve_css():
    try:
        with open("../frontend/style.css", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, media_type="text/css")
    except FileNotFoundError:
        return HTMLResponse(content="", status_code=404)

@app.get("/script.js")
async def serve_js():
    try:
        with open("../frontend/script.js", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, media_type="text/javascript")
    except FileNotFoundError:
        return HTMLResponse(content="", status_code=404)

@app.post("/search", response_model=SearchResponse)
async def search_papers(keywords: str = Form(...)):
    try:
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
        if not keyword_list:
            raise HTTPException(status_code=400, detail="No keywords provided")
        
        search_query = ' OR '.join(keyword_list)
        print(f"🔍 Searching arXiv: {search_query}")
        
        client = arxiv.Client()
        search = arxiv.Search(
            query=search_query,
            max_results=20,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        papers = list(client.results(search))
        if not papers:
            raise HTTPException(status_code=404, detail="No papers found")
        
        # Calculate relevance scores
        keywords_text = ' '.join(keyword_list)
        scored_papers = []
        for paper in papers:
            relevance_score = calculate_relevance_score(
                keywords_text, 
                f"{paper.title} {paper.summary or ''}"
            )
            scored_papers.append({
                "paper": paper,
                "relevance_score": relevance_score,
                "keywords_match": len(set(keyword_list) & set(preprocess_text(paper.title + " " + (paper.summary or "")).split()))
            })
        
        # Sort by relevance score
        scored_papers.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        paper_list = []
        top_paper_list = []
        for i, scored_paper in enumerate(scored_papers[:20], 1):
            paper_data = {
                "id": i,
                "title": scored_paper['paper'].title,
                "published": scored_paper['paper'].published.strftime('%Y-%m-%d') if scored_paper['paper'].published else 'N/A',
                "pdf_url": scored_paper['paper'].pdf_url,
                "entry_id": scored_paper['paper'].entry_id,
                "authors": [author.name for author in scored_paper['paper'].authors],
                "summary": scored_paper['paper'].summary[:200] + "..." if scored_paper['paper'].summary else "",
                "relevance_score": round(scored_paper['relevance_score'], 4),
                "is_top": i <= 5
            }
            paper_list.append(paper_data)
            
            if i <= 5:
                top_paper_list.append(paper_data)
        
        print(f"✅ Found {len(paper_list)} papers, {len(top_paper_list)} top papers")
        return SearchResponse(papers=paper_list, top_papers=top_paper_list, total=len(paper_list))
    
    except Exception as e:
        print(f"❌ Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/paper/{paper_id}", response_class=HTMLResponse)
async def paper_detail(paper_id: int, keywords: str = Query("")):
    try:
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
        search_query = ' OR '.join(keyword_list) if keyword_list else "machine learning"
        
        client = arxiv.Client()
        search = arxiv.Search(query=search_query, max_results=50)
        papers = list(client.results(search))
        
        if paper_id > len(papers):
            raise HTTPException(status_code=404, detail="Paper not found")
        
        paper = papers[paper_id - 1]
        
        safe_title = paper.title.replace('<', '&lt;').replace('>', '&gt;')
        safe_summary = paper.summary.replace('<', '&lt;').replace('>', '&gt;') if paper.summary else ""
        safe_authors = ', '.join([a.name.replace('<', '&lt;').replace('>', '&gt;') for a in paper.authors])
        
        encoded_keywords = urllib.parse.quote(keywords)
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title}</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #ffffff , #ffffff 100%);
            min-height: 100vh; 
            padding: 20px;
        }}
        .paper-detail {{
            max-width: 1000px; margin: 0 auto; background: white; 
            border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #111827, #111827 100%);
            color: white; padding: 40px; text-align: center; position: relative;
        }}
        .back-btn, .summarize-btn {{
            display: inline-flex; align-items: center; gap: 10px;
            padding: 12px 24px; color: white;
            text-decoration: none; border-radius: 12px; margin: 0 10px 20px;
            font-weight: 600; transition: all 0.3s ease;
        }}
        .back-btn {{ background: #6c757d; }}
        .back-btn:hover {{ background: #5a6268; transform: translateY(-2px); }}
        .summarize-btn {{ 
            background: linear-gradient(135deg, #28a745, #20c997); 
            border: none; cursor: pointer;
        }}
        .summarize-btn:hover {{ 
            transform: translateY(-2px); box-shadow: 0 10px 20px rgba(40,167,69,0.3);
        }}
        .paper-meta {{
            background: #f8f9ff; padding: 30px; border-radius: 0 0 20px 20px;
        }}
        .paper-meta h1 {{ font-size: 1.8em; margin-bottom: 20px; color: #333; }}
        .meta-row {{ margin-bottom: 15px; }}
        .meta-label {{ font-weight: 600; color: #666; }}
        .paper-summary {{
            padding: 30px; line-height: 1.7;
        }}
        .paper-summary h3 {{ color: #4facfe; margin-bottom: 20px; font-size: 1.3em; }}
        .paper-actions {{
            padding: 30px; background: #f8f9ff; display: flex; gap: 20px;
            border-top: 1px solid #e1e5e9;
        }}
        .download-btn {{
            flex: 1; padding: 18px 30px; border: none; border-radius: 12px;
            font-size: 16px; font-weight: 600; cursor: pointer; text-decoration: none;
            display: inline-flex; align-items: center; justify-content: center; gap: 10px;
            transition: all 0.3s ease;
        }}
        .download-pdf {{ background: #28a745; color: white; }}
        .download-pdf:hover {{ background: #218838; transform: translateY(-2px); }}
        .arxiv-link {{ background: #007bff; color: white; }}
        .arxiv-link:hover {{ background: #0056b3; transform: translateY(-2px); }}
        @media (max-width: 768px) {{
            .paper-actions {{ flex-direction: column; }}
            .header {{ padding: 20px; }}
            .back-btn, .summarize-btn {{ margin: 5px; display: block; text-align: center; }}
            .paper-detail {{ margin: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="paper-detail">
        <div class="header">
            <a href="/?keywords={encoded_keywords}" class="back-btn">
                <i class="fas fa-arrow-left"></i> Back to Search
            </a>
            <button onclick="window.location.href='/summarize/{paper_id}?keywords={encoded_keywords}'" class="summarize-btn">
                <i class="fas fa-file-alt"></i> Summarize Paper
            </button>
            <h1>{safe_title}</h1>
        </div>
        
        <div class="paper-meta">
            <div class="meta-row">
                <span class="meta-label">📚 Authors:</span> 
                <span>{safe_authors}</span>
            </div>
            <div class="meta-row">
                <span class="meta-label">📅 Published:</span> 
                <span>{paper.published.strftime('%Y-%m-%d') if paper.published else 'N/A'}</span>
            </div>
            <div class="meta-row">
                <span class="meta-label">🔗 arXiv ID:</span> 
                <a href="{paper.entry_id}" target="_blank">{paper.entry_id}</a>
            </div>
        </div>
        
        <div class="paper-summary">
            <h3>📝 Abstract</h3>
            <p>{safe_summary}</p>
        </div>
        
        <div class="paper-actions">
            <a href="/download/{paper_id}?keywords={encoded_keywords}" class="download-btn download-pdf">
                <i class="fas fa-download"></i> Download PDF
            </a>
            <a href="{paper.pdf_url}" class="download-btn arxiv-link" target="_blank">
                <i class="fas fa-external-link-alt"></i> View on arXiv
            </a>
        </div>
    </div>
</body>
</html>
        """
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        print(f"❌ Paper detail error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summarize/{paper_id}", response_class=HTMLResponse)
async def summarize_paper(paper_id: int, keywords: str = Query("")):
    try:
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
        search_query = ' OR '.join(keyword_list) if keyword_list else "machine learning"
        
        client = arxiv.Client()
        search = arxiv.Search(query=search_query, max_results=50)
        papers = list(client.results(search))
        
        if paper_id > len(papers):
            raise HTTPException(status_code=404, detail="Paper not found")
        
        paper = papers[paper_id - 1]
        
        # Generate summary (extract key sentences)
        summary = generate_summary(paper.summary or "")
        
        safe_title = paper.title.replace('<', '&lt;').replace('>', '&gt;')
        safe_full_summary = (paper.summary or "").replace('<', '&lt;').replace('>', '&gt;')
        safe_summary = summary.replace('<', '&lt;').replace('>', '&gt;')
        safe_authors = ', '.join([a.name.replace('<', '&lt;').replace('>', '&gt;') for a in paper.authors])
        
        encoded_keywords = urllib.parse.quote(keywords)
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title} - Summary</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: white;
            min-height: 100vh; 
            padding: 20px;
        }}
        .summary-container {{
            max-width: 900px; margin: 0 auto; background: white; 
            border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #475569, #764ba2);
            color: white; padding: 40px; text-align: center;
        }}
        .back-btn {{
            display: inline-flex; align-items: center; gap: 10px;
            padding: 12px 24px; background: rgba(255,255,255,0.2); 
            color: white; text-decoration: none; border-radius: 12px; 
            font-weight: 600; transition: all 0.3s ease; backdrop-filter: blur(10px);
        }}
        .back-btn:hover {{ background: rgba(255,255,255,0.3); transform: translateY(-2px); }}
        .summary-content {{
            padding: 40px; line-height: 1.8;
        }}
        .summary-content h1 {{ color: #333; margin-bottom: 30px; font-size: 2em; }}
        .summary-content h2 {{ color: #667eea; margin: 30px 0 15px; font-size: 1.5em; }}
        .summary-section {{
            background: #f8f9ff; padding: 25px; border-radius: 15px; margin: 20px 0;
            border-left: 5px solid #ffffff;
        }}
        .highlight {{ background: linear-gradient(120deg, #a8edea 0%, #fed6e3 100%); padding: 15px; border-radius: 10px; }}
        .meta-info {{ background: #e8f4f8; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        .meta-row {{ margin-bottom: 10px; }}
        .meta-label {{ font-weight: 600; color: #555; }}
        @media (max-width: 768px) {{
            .summary-content {{ padding: 20px; }}
            .header {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="summary-container">
        <div class="header">
            <a href="/paper/{paper_id}?keywords={encoded_keywords}" class="back-btn">
                <i class="fas fa-arrow-left"></i> Back to Paper
            </a>
            <h1>📚 Paper Summary</h1>
        </div>
        
        <div class="summary-content">
            <div class="meta-info">
                <div class="meta-row">
                    <span class="meta-label">📖 Title:</span> 
                    <strong>{safe_title}</strong>
                </div>
                <div class="meta-row">
                    <span class="meta-label">📚 Authors:</span> 
                    <span>{safe_authors}</span>
                </div>
                <div class="meta-row">
                    <span class="meta-label">📅 Published:</span> 
                    <span>{paper.published.strftime('%Y-%m-%d') if paper.published else 'N/A'}</span>
                </div>
            </div>
            
            <div class="summary-section highlight">
                <h2>✨ Key Summary</h2>
                <p><strong>{safe_summary}</strong></p>
            </div>
            
            <div class="summary-section">
                <h2>📄 Full Abstract</h2>
                <p>{safe_full_summary}</p>
            </div>
        </div>
    </div>
</body>
</html>
        """
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        print(f"❌ Summary error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def generate_summary(text, max_sentences=4):
    """Generate simple extractive summary without scikit-learn"""
    if not text or len(text.split('.')) < 3:
        return text[:500] + "..." if len(text) > 500 else text
    
    sentences = nltk.sent_tokenize(text)
    
    # Simple scoring: sentence length + keyword presence
    scores = []
    for sentence in sentences:
        score = len(sentence.split())  # Length score
        # Bonus for important words (first words, numbers, etc.)
        if any(word in sentence.lower() for word in ['method', 'result', 'approach', 'propose', 'show', 'demonstrate']):
            score += 10
        if re.search(r'\b\d+\b', sentence):
            score += 5
        scores.append(score)
    
    # Select top sentences
    top_indices = np.argsort(scores)[-max_sentences:]
    top_indices = sorted(top_indices)
    
    summary_sentences = [sentences[i].strip() for i in top_indices]
    return ' '.join(summary_sentences)

@app.post("/download/{paper_id}")
async def download_paper(paper_id: int, keywords: str = Form(...)):
    try:
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
        search_query = ' OR '.join(keyword_list)
        
        client = arxiv.Client()
        search = arxiv.Search(query=search_query, max_results=50)
        papers = list(client.results(search))
        
        if paper_id > len(papers):
            raise HTTPException(status_code=404, detail="Paper not found")
        
        paper = papers[paper_id - 1]
        safe_filename = re.sub(r'[^\w\s-]', '', paper.title)[:50].strip()
        safe_filename = re.sub(r'\s+', '_', safe_filename) + f"_{paper_id:02d}.pdf"
        pdf_path = paper.download_pdf(dirpath='papers/', filename=safe_filename)
        
        print(f"📥 Downloaded: {safe_filename}")
        return {"filename": safe_filename, "path": f"/papers/{safe_filename}"}
    
    except Exception as e:
        print(f"❌ Download error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "papers_dir": os.path.exists("papers")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
