"""
Phase 2 -- Ingestion: typed request model.

This file is provided as-is (it's schema, not logic). The work is in
parser.py: turning an untrusted raw dict into one of these, safely.
"""
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class SupportingDocument(BaseModel):
    doc_type: str
    url: str


class PriorAuthRequest(BaseModel):
    request_id: str
    patient_id: str
    provider_npi: str = Field(..., min_length=10, max_length=10)
    payer_id: str
    procedure_code: str = Field(..., pattern=r"^\d{5}$")  # CPT code, 5 digits
    diagnosis_code: str  # ICD-10 code
    supporting_documents: List[SupportingDocument] = []
    submitted_at: datetime
