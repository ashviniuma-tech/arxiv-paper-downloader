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

app = FastAPI(title="arXiv Paper Downloader")

# ✅ CORS - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Create papers directory
os.makedirs('papers', exist_ok=True)
app.mount("/papers", StaticFiles(directory="papers"), name="papers")

class SearchResponse(BaseModel):
    papers: List[dict]
    total: int

# ✅ Serve main frontend
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

# ✅ Serve CSS
@app.get("/style.css")
async def serve_css():
    try:
        with open("../frontend/style.css", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, media_type="text/css")
    except FileNotFoundError:
        return HTMLResponse(content="", status_code=404)

# ✅ Serve JS
@app.get("/script.js")
async def serve_js():
    try:
        with open("../frontend/script.js", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, media_type="text/javascript")
    except FileNotFoundError:
        return HTMLResponse(content="", status_code=404)

# ✅ Search endpoint
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
        
        paper_list = []
        for i, paper in enumerate(papers[:20], 1):
            paper_list.append({
                "id": i,
                "title": paper.title,
                "published": paper.published.strftime('%Y-%m-%d') if paper.published else 'N/A',
                "pdf_url": paper.pdf_url,
                "entry_id": paper.entry_id,
                "authors": [author.name for author in paper.authors],
                "summary": paper.summary[:200] + "..." if paper.summary else ""
            })
        
        print(f"✅ Found {len(paper_list)} papers")
        return SearchResponse(papers=paper_list, total=len(paper_list))
    
    except Exception as e:
        print(f"❌ Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ NEW: Paper detail page
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
        
        # Escape HTML characters
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
            color: white; padding: 40px; text-align: center;
        }}
        .back-btn {{
            display: inline-flex; align-items: center; gap: 10px;
            padding: 12px 24px; background: #6c757d; color: white;
            text-decoration: none; border-radius: 12px; margin-bottom: 20px;
            font-weight: 600; transition: all 0.3s ease;
        }}
        .back-btn:hover {{ background: #5a6268; transform: translateY(-2px); }}
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

# ✅ Download endpoint
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
