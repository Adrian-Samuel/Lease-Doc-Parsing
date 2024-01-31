import shutil
from typing import List

import pdfplumber
from fastapi import FastAPI, File, HTTPException, UploadFile

from src.lease import LeaseDocument, LeaseParser

app = FastAPI()


@app.post("/documents/upload/lease", response_model=List[LeaseDocument])
async def upload_pdf(pdf: UploadFile = File(...)):
    if pdf.content_type != "application/pdf":
        raise HTTPException(
            status_code=400, detail="Invalid file type. Please upload a PDF file."
        )

    # create a tmp file
    with open(pdf.filename, "wb") as buffer:
        shutil.copyfileobj(pdf.file, buffer)

    with pdfplumber.open(pdf.filename) as pdf_file:
        return LeaseParser().marshal_lease_data(pdf_file)
