from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from kanoon_client import KanoonClient
from masking_engine import SmartMasker
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="."), name="static")

# Initialize Logic
client = KanoonClient()
masker = SmartMasker()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, query: str = Form(...)):
    results = client.search_documents(query)
    docs = results.get('docs', [])
    return templates.TemplateResponse("index.html", {"request": request, "docs": docs, "query": query})

@app.get("/process/{doc_id}", response_class=HTMLResponse)
async def process_doc(request: Request, doc_id: int):
    # 1. Fetch
    raw_data = client.get_document(doc_id)
    original_text = raw_data.get('doc', 'Error fetching document')
    title = raw_data.get('title', 'Unknown Title')

    # 2. Mask (now returns tuple: masked_text, analysis)
    masked_text, analysis = masker.mask_victims_and_family(original_text)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "doc_id": doc_id,
        "title": title,
        "original_text": original_text,
        "masked_text": masked_text,
        "view_mode": "compare",
        "analysis": analysis
    })

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)