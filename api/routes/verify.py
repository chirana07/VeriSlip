"""
Verification API Route for VeriSlip.
Receives bank slip image uploads, runs multi-layer forensic detection, and returns verdicts.
"""

import math
from functools import partial
from datetime import date
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool
from typing import Optional, List
from core.forensics.unified_scorer import VeriSlipForensicEngine
from core.forensics.ocr_extractor import ReceiptFieldExtractor
from core.forensics.utils import pil_to_cv2
from core.templates.lankaqr_parser import (
    detect_and_decode_qr_from_image,
    parse_lankaqr,
    cross_verify_lankaqr_with_receipt,
)
from core.security.image_sanitizer import (
    ImageValidationError,
    MAX_IMAGE_UPLOAD_BYTES,
    sanitize_image_bytes,
    _check_dimensions,
)
from core.jobs.forensic_jobs import ForensicJobManager, JobQueueFullError
from core.history.verification_history import InMemoryVerificationHistoryStore
from core.observability.logging import get_correlation_id
from api.schemas.detection import (
    VerificationResponse,
    BatchVerificationResponse,
    BatchSlipItem,
    BatchVerificationSummary,
    ForensicJobSubmissionResponse,
    ForensicJobStatusResponse,
    VerificationHistoryResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Verification"])
engine = VeriSlipForensicEngine()
field_extractor = ReceiptFieldExtractor()
job_manager = ForensicJobManager()
history_store = InMemoryVerificationHistoryStore()


class ForensicAnalysisError(RuntimeError):
    """Internal marker for safely handled forensic engine failures."""


async def _read_bounded_upload(file: UploadFile) -> bytes:
    """Read a bounded upload and promptly close its secure spool handle."""
    try:
        contents = await file.read(MAX_IMAGE_UPLOAD_BYTES + 1)
        if len(contents) > MAX_IMAGE_UPLOAD_BYTES:
            raise ImageValidationError(
                "Upload exceeds the permitted size.", status_code=413
            )
        return contents
    finally:
        await file.close()


def _batch_upload_label(index: int) -> str:
    """Return an internal display identifier instead of an untrusted filename."""
    return f"upload_{index:03d}"


def _is_pdf(contents: bytes) -> bool:
    """Identify PDFs by their file signature, never their name or MIME type."""
    return contents.startswith(b"%PDF-")


def _decode_document(contents: bytes):
    """Bound PDF rasterization before allocation and always release native handles."""
    if not _is_pdf(contents):
        return sanitize_image_bytes(contents)

    import pypdfium2 as pdfium

    with pdfium.PdfDocument(contents) as pdf:
        if len(pdf) == 0:
            raise ImageValidationError("Uploaded PDF contains no pages.")
        page = pdf[0]
        try:
            width, height = page.get_size()
            if not all(math.isfinite(value) and value > 0 for value in (width, height)):
                raise ImageValidationError("PDF page dimensions are invalid.")
            _check_dimensions(math.ceil(width * 2), math.ceil(height * 2))
            bitmap = page.render(scale=2.0)
            try:
                image = bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
        finally:
            page.close()
        try:
            image.info["pdf_metadata"] = pdf.get_metadata_dict()
        except Exception:
            pass
        return image


def _analyze_image(
    pil_img,
    bank_code: Optional[str] = None,
    reference_no: Optional[str] = None,
    include_heatmaps: bool = True,
):
    """Run OCR and forensic inference away from the FastAPI event loop."""
    extracted_meta = field_extractor.extract_fields(pil_img, bank_hint=bank_code)
    effective_bank = bank_code or extracted_meta["detected_bank_code"]
    try:
        results = engine.analyze(
            pil_image=pil_img,
            bank_code=effective_bank,
            reference_no=reference_no,
            include_heatmaps=include_heatmaps,
        )
    except Exception:
        raise ForensicAnalysisError from None
    results["extracted_metadata"] = extracted_meta

    # Cross-verify LankaQR payload if QR code is present on the slip (#122)
    cv2_img = pil_to_cv2(pil_img)
    qr_text = detect_and_decode_qr_from_image(cv2_img)
    lankaqr_res = None
    if qr_text:
        parsed_qr = parse_lankaqr(qr_text)
        lankaqr_res = cross_verify_lankaqr_with_receipt(
            qr_data=parsed_qr,
            receipt_amount=extracted_meta.get("amount"),
            receipt_reference=reference_no or extracted_meta.get("reference_no")
        )
        if lankaqr_res.get("is_tampered", False):
            results["findings_summary"].extend(lankaqr_res.get("discrepancies", []))
            results["tamper_risk_percentage"] = max(results.get("tamper_risk_percentage", 0.0), 85.0)
            results["verdict"] = "HIGH_RISK_TAMPERED"
            results["verdict_color"] = "#ef4444"

    results["lankaqr_validation"] = lankaqr_res
    return results


def _record_verification(owner_key_id: str, reference_no: Optional[str], result):
    """Persist only merchant-facing summary metadata from a successful result."""
    extracted = result.get("extracted_metadata") or {}
    history_store.add(
        owner_key_id,
        reference_no=reference_no,
        verdict=result.get("verdict", "UNKNOWN"),
        tamper_risk_percentage=result.get("tamper_risk_percentage", 0.0),
        bank_code=extracted.get("detected_bank_code"),
        bank_name=extracted.get("bank_name"),
    )

@router.post("/verify", response_model=VerificationResponse)
async def verify_slip(
    request: Request,
    file: UploadFile = File(..., description="Payment slip or screenshot image file"),
    bank_code: Optional[str] = Form(None, description="Optional bank code: COMBANK, SAMPATH, BOC, HNB, SEYLAN, NTB_FRIMI, GENERIC_CEFTS"),
    reference_no: Optional[str] = Form(None, max_length=128, description="Optional transaction reference number for syntax verification")
):
    """
    Run multi-layer forensic analysis on an uploaded payment slip image.
    Automatically detects bank layout and key fields if not provided.
    """
    try:
        contents = await _read_bounded_upload(file)
        pil_img = await run_in_threadpool(_decode_document, contents)
    except ImageValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except Exception:
        raise HTTPException(
            status_code=400, detail="Uploaded document could not be decoded safely."
        ) from None

    try:
        result = await run_in_threadpool(
            _analyze_image, pil_img, bank_code, reference_no, True
        )
        await run_in_threadpool(
            _record_verification, request.state.api_key_id, reference_no, result
        )
        return result
    except ForensicAnalysisError:
        raise HTTPException(
            status_code=500, detail="Forensic analysis could not be completed."
        ) from None


@router.post(
    "/verify/jobs", response_model=ForensicJobSubmissionResponse, status_code=202
)
async def submit_verification_job(
    request: Request,
    file: UploadFile = File(..., description="Payment slip or screenshot image file"),
    bank_code: Optional[str] = Form(None),
    reference_no: Optional[str] = Form(None, max_length=128),
):
    """Sanitize an upload, then queue heavy OCR and forensic analysis."""
    try:
        contents = await _read_bounded_upload(file)
        pil_img = await run_in_threadpool(_decode_document, contents)
    except ImageValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except Exception:
        raise HTTPException(
            status_code=400, detail="Uploaded document could not be decoded safely."
        ) from None

    correlation_id = get_correlation_id() or request.state.correlation_id
    owner_key_id = request.state.api_key_id
    task = partial(_analyze_image, pil_img, bank_code, reference_no, True)
    try:
        job = job_manager.submit(
            owner_key_id,
            correlation_id,
            task,
            on_complete=partial(_record_verification, owner_key_id, reference_no),
        )
    except JobQueueFullError:
        raise HTTPException(
            status_code=503, detail="Forensic job capacity is temporarily unavailable."
        ) from None
    return {
        "job_id": job.job_id,
        "status": job.status,
        "status_url": f"/api/v1/verify/jobs/{job.job_id}",
        "correlation_id": job.correlation_id,
    }


@router.get("/verify/jobs/{job_id}", response_model=ForensicJobStatusResponse)
async def get_verification_job(request: Request, job_id: str):
    """Return a queued job only to the API key that created it."""
    job = job_manager.get(job_id, request.state.api_key_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Forensic job was not found.")
    return job


@router.get(
    "/verifications/history", response_model=VerificationHistoryResponse
)
async def get_verification_history(
    request: Request,
    reference: Optional[str] = Query(None, max_length=128),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Search the authenticated merchant's metadata-only verification history."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400, detail="date_from must be on or before date_to."
        )
    return history_store.search(
        request.state.api_key_id,
        reference_query=reference,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

@router.post("/batch-verify", response_model=BatchVerificationResponse)
async def batch_verify_slips(
    files: List[UploadFile] = File(..., description="Multiple payment slip images for batch forensic audit")
):
    """
    Execute high-throughput batch forensic audit on multiple slip images.
    Returns aggregate fraud rate, individual verdicts, and localized tamper signals.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded for batch verification.")

    if len(files) > 25:
        raise HTTPException(status_code=400, detail="Batch limit is 25 images per request.")

    items: List[BatchSlipItem] = []
    auth_cnt = 0
    susp_cnt = 0
    risk_cnt = 0
    total_risk = 0.0

    for index, f in enumerate(files, start=1):
        fname = _batch_upload_label(index)
        try:
            contents = await _read_bounded_upload(f)
            pil_img = await run_in_threadpool(_decode_document, contents)
            res = await run_in_threadpool(
                _analyze_image, pil_img, None, None, False
            )
            extracted = res["extracted_metadata"]
            effective_bank = extracted["detected_bank_code"]

            v = res["verdict"]
            risk_pct = res["tamper_risk_percentage"]
            total_risk += risk_pct

            if v == "AUTHENTIC":
                auth_cnt += 1
            elif v == "SUSPICIOUS":
                susp_cnt += 1
            else:
                risk_cnt += 1

            top_find = res["findings_summary"][0] if res["findings_summary"] else "Compliant slip signals"

            items.append(BatchSlipItem(
                filename=fname,
                verdict=v,
                verdict_color=res["verdict_color"],
                tamper_risk_percentage=risk_pct,
                detected_bank=effective_bank,
                bank_name=extracted["bank_name"],
                recommendation=res["recommendation"],
                flagged_regions_count=len(res.get("flagged_regions", [])),
                findings_count=len(res.get("findings_summary", [])),
                top_finding=top_find,
                extracted_metadata=extracted
            ))
        except Exception:
            items.append(BatchSlipItem(
                filename=fname,
                verdict="ERROR",
                verdict_color="#ef4444",
                tamper_risk_percentage=100.0,
                detected_bank="UNKNOWN",
                bank_name="Unknown Bank",
                recommendation="File was rejected because it is invalid or unsafe.",
                flagged_regions_count=0,
                findings_count=1,
                top_finding="Unreadable or corrupt image file"
            ))
            risk_cnt += 1
            total_risk += 100.0

    total_proc = len(items)
    avg_risk = round(total_risk / max(total_proc, 1), 1)
    fraud_rate = round(((susp_cnt + risk_cnt) / max(total_proc, 1)) * 100, 1)

    summary = BatchVerificationSummary(
        total_processed=total_proc,
        authentic_count=auth_cnt,
        suspicious_count=susp_cnt,
        high_risk_count=risk_cnt,
        avg_risk_percentage=avg_risk,
        fraud_rate_percentage=fraud_rate
    )

    return BatchVerificationResponse(summary=summary, items=items)
