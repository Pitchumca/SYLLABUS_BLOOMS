import json
import logging
import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.syllabus import Syllabus
from app.models.template_and_resource import (
    QuestionPaperTemplate,
    TemplateVersion,
    ExtractedBlueprint,
    BlueprintSectionModel,
    BlueprintQuestionSlotModel,
    SlotQuestionTypeModel
)
from app.schemas.template_and_resource import (
    CanonicalBlueprintSchema,
    FieldConfidenceScores,
    BlueprintValidationResult,
    TemplateExtractionResponse,
    TemplateSaveRequest,
    TemplateUpdateRequest,
    TemplateListItem,
    TemplateDetailResponse
)
from app.utils.auth import get_current_user, require_faculty
from app.utils.security import (
    sanitize_filename,
    generate_safe_stored_filename,
    validate_uploaded_file,
    validate_path_traversal
)
from app.services.template_extractor import (
    detect_file_format,
    extract_blueprint_from_file,
    validate_extracted_blueprint
)
from app.services.co_extractor import extract_course_outcomes, extract_syllabus_units

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/template", tags=["Question Paper Template & Blueprint Extraction"])


@router.post("/upload", response_model=TemplateExtractionResponse, status_code=status.HTTP_200_OK)
async def upload_and_extract_template(
    file: UploadFile = File(...),
    syllabus_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Upload institution question paper template (DOCX, PDF, Scanned PDF, PNG/JPG, XLSX).
    Extracts structure, examination metadata, sections, question numbering, marks,
    COs, Bloom levels, and OR relationships with confidence scoring.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    ext = Path(file.filename).suffix.lower()
    allowed_exts = {".docx", ".doc", ".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported template format '{ext}'. Allowed: DOCX, PDF, PNG, JPG, XLSX."
        )

    clean_name = sanitize_filename(file.filename)
    stored_name = generate_safe_stored_filename(clean_name)
    stored_path = settings.UPLOAD_DIR / stored_name
    validate_path_traversal(stored_path, settings.UPLOAD_DIR)

    # Stream file to storage
    header_chunk = await file.read(1024)
    file_size = len(header_chunk)
    with open(stored_path, "wb") as f:
        f.write(header_chunk)
        while chunk := await file.read(64 * 1024):
            file_size += len(chunk)
            if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
                f.close()
                stored_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Template file exceeds maximum size limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
                )
            f.write(chunk)

    detected_fmt = detect_file_format(stored_path)

    # Extract Blueprint & Confidence Scores
    try:
        raw_blueprint, conf_dict, preview_text = extract_blueprint_from_file(stored_path, detected_fmt)
    except Exception as e:
        logger.error(f"Template extraction error on {stored_path.name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract structure from template: {str(e)}"
        )

    # Check against selected syllabus if provided
    syllabus_cos = None
    syllabus_units = None
    if syllabus_id:
        syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
        if syllabus and syllabus.extracted_text:
            syllabus_cos = [co.get("code") for co in extract_course_outcomes(syllabus.extracted_text)]
            syllabus_units = [int(u.get("number", 1)) for u in extract_syllabus_units(syllabus.extracted_text) if str(u.get("number")).isdigit()]

    # Validate Extracted Blueprint
    val_res = validate_extracted_blueprint(raw_blueprint, syllabus_cos, syllabus_units)

    # Determine status
    has_low_conf = any(v < 0.85 for v in conf_dict.values())
    ext_status = "needs_verification" if (has_low_conf or not val_res["is_valid"] or detected_fmt in ["scanned_pdf", "image"]) else "extracted"

    canonical_blueprint = CanonicalBlueprintSchema(**raw_blueprint)
    field_confidence = FieldConfidenceScores(**conf_dict)
    validation_schema = BlueprintValidationResult(**val_res)

    return TemplateExtractionResponse(
        blueprint=canonical_blueprint,
        confidence_scores=field_confidence,
        validation=validation_schema,
        extraction_status=ext_status,
        file_format=detected_fmt,
        original_filename=clean_name,
        stored_filename=stored_name,
        raw_preview_text=preview_text[:2000] if preview_text else ""
    )


@router.post("/validate", response_model=BlueprintValidationResult)
def validate_blueprint_endpoint(
    blueprint: CanonicalBlueprintSchema,
    syllabus_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Validate a faculty-corrected or constructed blueprint JSON against all Specification B6 rules.
    """
    syllabus_cos = None
    syllabus_units = None
    if syllabus_id:
        syllabus = db.query(Syllabus).filter(Syllabus.id == syllabus_id).first()
        if syllabus and syllabus.extracted_text:
            syllabus_cos = [co.get("code") for co in extract_course_outcomes(syllabus.extracted_text)]
            syllabus_units = [int(u.get("number", 1)) for u in extract_syllabus_units(syllabus.extracted_text) if str(u.get("number")).isdigit()]

    val_res = validate_extracted_blueprint(blueprint.model_dump(), syllabus_cos, syllabus_units)
    return BlueprintValidationResult(**val_res)


@router.post("/save", response_model=TemplateDetailResponse, status_code=status.HTTP_201_CREATED)
def save_template_to_library(
    payload: TemplateSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Save verified and confirmed blueprint into the Reusable Template Library.
    """
    blueprint_dict = payload.blueprint.model_dump()
    val_res = validate_extracted_blueprint(blueprint_dict)

    template = QuestionPaperTemplate(
        name=payload.template_name,
        institution=payload.institution or payload.blueprint.institution,
        department=payload.department or payload.blueprint.department,
        programme=payload.programme or payload.blueprint.programme,
        regulation=payload.regulation,
        exam_name=payload.exam_name or payload.blueprint.exam_name,
        exam_type=payload.exam_type or payload.blueprint.exam_type,
        max_marks=payload.maximum_marks or payload.blueprint.maximum_marks,
        duration_minutes=payload.duration_minutes or payload.blueprint.duration_minutes,
        academic_year=payload.academic_year,
        course_code=payload.course_code or payload.blueprint.course_code,
        course_title=payload.course_title or payload.blueprint.course_title,
        version=1,
        owner_id=current_user.id,
        approved_by_id=current_user.id,
        approval_date=datetime.datetime.utcnow(),
        is_active=True,
        is_department_default=bool(payload.is_department_default),
        is_course_default=bool(payload.is_course_default),
        original_filename=payload.original_filename,
        stored_filename=payload.stored_filename,
        file_format=payload.file_format or "docx",
        instructions="\n".join(payload.blueprint.instructions) if payload.blueprint.instructions else None
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    # Record initial Version
    t_version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        blueprint_json=json.dumps(blueprint_dict),
        stored_filename=payload.stored_filename,
        changed_by_id=current_user.id,
        change_summary="Initial template creation and confirmation"
    )
    db.add(t_version)

    # Save ExtractedBlueprint record
    ext_bp = ExtractedBlueprint(
        template_id=template.id,
        canonical_blueprint_json=json.dumps(blueprint_dict),
        extraction_status="confirmed",
        validation_errors_json=json.dumps(val_res["errors"]),
        validation_warnings_json=json.dumps(val_res["warnings"]),
        verified_by_id=current_user.id,
        verified_at=datetime.datetime.utcnow()
    )
    db.add(ext_bp)
    db.commit()
    db.refresh(ext_bp)

    # Populate normalized BlueprintSectionModel and BlueprintQuestionSlotModel
    for s_idx, sec in enumerate(payload.blueprint.sections):
        sec_model = BlueprintSectionModel(
            blueprint_id=ext_bp.id,
            section_name=sec.section_name,
            answer_rule=sec.answer_rule,
            start_question_number=sec.start_question_number or 1,
            question_count=sec.question_count,
            marks_per_question=sec.marks_per_question,
            section_total=sec.section_total,
            or_choice=sec.or_choice,
            order_index=s_idx
        )
        db.add(sec_model)
        db.commit()
        db.refresh(sec_model)

        for q in sec.questions:
            slot_model = BlueprintQuestionSlotModel(
                section_id=sec_model.id,
                question_number=q.question_number,
                or_pair_id=q.or_pair_id,
                unit_number=q.unit,
                co_level=q.co,
                bloom_level=q.bloom_level,
                marks=q.marks,
                allowed_types_json=json.dumps(q.question_types),
                required_types_json=json.dumps(q.question_types),
                preferred_type=q.preferred_type or (q.question_types[0] if q.question_types else "short_answer"),
                combine_types=bool(q.combine_types),
                confidence_score=q.confidence_score or 1.0,
                needs_review=bool(q.needs_review),
                remarks=q.remarks
            )
            db.add(slot_model)

    db.commit()
    db.refresh(template)

    return TemplateDetailResponse(
        id=template.id,
        name=template.name,
        institution=template.institution,
        department=template.department,
        programme=template.programme,
        regulation=template.regulation,
        exam_name=template.exam_name,
        exam_type=template.exam_type,
        max_marks=template.max_marks,
        duration_minutes=template.duration_minutes,
        academic_year=template.academic_year,
        course_code=template.course_code,
        course_title=template.course_title,
        version=template.version,
        owner_id=template.owner_id,
        owner_name=current_user.full_name,
        is_active=template.is_active,
        is_department_default=template.is_department_default,
        is_course_default=template.is_course_default,
        file_format=template.file_format,
        original_filename=template.original_filename,
        created_at=template.created_at,
        updated_at=template.updated_at,
        blueprint=payload.blueprint,
        validation=BlueprintValidationResult(**val_res),
        extraction_status="confirmed"
    )


@router.get("/library", response_model=List[TemplateListItem])
def list_template_library(
    course_code: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    List reusable templates from the library.
    """
    query = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.is_active == True)
    if course_code:
        query = query.filter(QuestionPaperTemplate.course_code.ilike(f"%{course_code}%"))
    if exam_type:
        query = query.filter(QuestionPaperTemplate.exam_type == exam_type)

    templates = query.order_by(QuestionPaperTemplate.updated_at.desc()).all()
    results = []
    for t in templates:
        owner_name = t.owner.full_name if t.owner else "Faculty"
        item = TemplateListItem(
            id=t.id,
            name=t.name,
            institution=t.institution,
            department=t.department,
            programme=t.programme,
            regulation=t.regulation,
            exam_name=t.exam_name,
            exam_type=t.exam_type,
            max_marks=t.max_marks,
            duration_minutes=t.duration_minutes,
            academic_year=t.academic_year,
            course_code=t.course_code,
            course_title=t.course_title,
            version=t.version,
            owner_id=t.owner_id,
            owner_name=owner_name,
            is_active=t.is_active,
            is_department_default=t.is_department_default,
            is_course_default=t.is_course_default,
            file_format=t.file_format,
            original_filename=t.original_filename,
            created_at=t.created_at,
            updated_at=t.updated_at
        )
        results.append(item)
    return results


@router.get("/{template_id}", response_model=TemplateDetailResponse)
def get_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Retrieve single template details and its active canonical blueprint.
    """
    template = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    ext_bp = db.query(ExtractedBlueprint).filter(ExtractedBlueprint.template_id == template.id).order_by(ExtractedBlueprint.id.desc()).first()
    if not ext_bp:
        raise HTTPException(status_code=404, detail="Extracted blueprint for template not found.")

    bp_dict = json.loads(ext_bp.canonical_blueprint_json)
    val_res = validate_extracted_blueprint(bp_dict)

    owner_name = template.owner.full_name if template.owner else "Faculty"

    return TemplateDetailResponse(
        id=template.id,
        name=template.name,
        institution=template.institution,
        department=template.department,
        programme=template.programme,
        regulation=template.regulation,
        exam_name=template.exam_name,
        exam_type=template.exam_type,
        max_marks=template.max_marks,
        duration_minutes=template.duration_minutes,
        academic_year=template.academic_year,
        course_code=template.course_code,
        course_title=template.course_title,
        version=template.version,
        owner_id=template.owner_id,
        owner_name=owner_name,
        is_active=template.is_active,
        is_department_default=template.is_department_default,
        is_course_default=template.is_course_default,
        file_format=template.file_format,
        original_filename=template.original_filename,
        created_at=template.created_at,
        updated_at=template.updated_at,
        blueprint=CanonicalBlueprintSchema(**bp_dict),
        validation=BlueprintValidationResult(**val_res),
        extraction_status=ext_bp.extraction_status
    )


@router.put("/{template_id}", response_model=TemplateDetailResponse)
def update_template(
    template_id: int,
    payload: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Update an existing template, increment version, and record version history.
    Enforces authorization check: Only the template owner or Admin may overwrite an approved template.
    """
    template = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    # Authorization Check (Specification B7)
    if current_user.role != "admin" and template.owner_id and template.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You cannot overwrite another faculty member's approved template."
        )

    if payload.template_name is not None:
        template.name = payload.template_name
    if payload.institution is not None:
        template.institution = payload.institution
    if payload.department is not None:
        template.department = payload.department
    if payload.programme is not None:
        template.programme = payload.programme
    if payload.regulation is not None:
        template.regulation = payload.regulation
    if payload.exam_name is not None:
        template.exam_name = payload.exam_name
    if payload.exam_type is not None:
        template.exam_type = payload.exam_type
    if payload.maximum_marks is not None:
        template.max_marks = payload.maximum_marks
    if payload.duration_minutes is not None:
        template.duration_minutes = payload.duration_minutes
    if payload.academic_year is not None:
        template.academic_year = payload.academic_year
    if payload.is_active is not None:
        template.is_active = payload.is_active
    if payload.is_department_default is not None:
        template.is_department_default = payload.is_department_default
    if payload.is_course_default is not None:
        template.is_course_default = payload.is_course_default

    # Increment Version
    template.version += 1
    template.updated_at = datetime.datetime.utcnow()

    # Update Blueprint JSON & Version log if new blueprint supplied
    ext_bp = db.query(ExtractedBlueprint).filter(ExtractedBlueprint.template_id == template.id).order_by(ExtractedBlueprint.id.desc()).first()
    if payload.blueprint:
        bp_dict = payload.blueprint.model_dump()
        val_res = validate_extracted_blueprint(bp_dict)
        
        ext_bp.canonical_blueprint_json = json.dumps(bp_dict)
        ext_bp.extraction_status = "faculty_corrected"
        ext_bp.validation_errors_json = json.dumps(val_res["errors"])
        ext_bp.validation_warnings_json = json.dumps(val_res["warnings"])
        ext_bp.verified_by_id = current_user.id
        ext_bp.verified_at = datetime.datetime.utcnow()

        t_version = TemplateVersion(
            template_id=template.id,
            version_number=template.version,
            blueprint_json=json.dumps(bp_dict),
            stored_filename=template.stored_filename,
            changed_by_id=current_user.id,
            change_summary=payload.change_summary or "Updated blueprint parameters"
        )
        db.add(t_version)
    else:
        bp_dict = json.loads(ext_bp.canonical_blueprint_json)
        val_res = validate_extracted_blueprint(bp_dict)

    db.commit()
    db.refresh(template)

    owner_name = template.owner.full_name if template.owner else "Faculty"

    return TemplateDetailResponse(
        id=template.id,
        name=template.name,
        institution=template.institution,
        department=template.department,
        programme=template.programme,
        regulation=template.regulation,
        exam_name=template.exam_name,
        exam_type=template.exam_type,
        max_marks=template.max_marks,
        duration_minutes=template.duration_minutes,
        academic_year=template.academic_year,
        course_code=template.course_code,
        course_title=template.course_title,
        version=template.version,
        owner_id=template.owner_id,
        owner_name=owner_name,
        is_active=template.is_active,
        is_department_default=template.is_department_default,
        is_course_default=template.is_course_default,
        file_format=template.file_format,
        original_filename=template.original_filename,
        created_at=template.created_at,
        updated_at=template.updated_at,
        blueprint=CanonicalBlueprintSchema(**bp_dict),
        validation=BlueprintValidationResult(**val_res),
        extraction_status=ext_bp.extraction_status
    )


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Delete or archive a template. Requires owner or admin authorization.
    """
    template = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    if current_user.role != "admin" and template.owner_id and template.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You cannot delete another faculty member's template."
        )

    db.delete(template)
    db.commit()
    return {"message": "Template removed successfully."}


@router.get("/{template_id}/download-original")
def download_original_template_file(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Download the original uploaded template file (DOCX, PDF, etc.).
    """
    template = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    if not template.stored_filename:
        raise HTTPException(status_code=404, detail="No original template file stored.")

    file_path = settings.UPLOAD_DIR / template.stored_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Template file not found on disk.")

    media_type = "application/octet-stream"
    if template.file_format == "docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif template.file_format == "pdf":
        media_type = "application/pdf"

    return FileResponse(
        path=str(file_path),
        filename=template.original_filename or f"template_{template.id}.docx",
        media_type=media_type
    )


@router.get("/{template_id}/export-blueprint-json")
def export_blueprint_json(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Download the canonical extracted blueprint JSON specification conforming to Section B4.
    """
    template = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    ext_bp = db.query(ExtractedBlueprint).filter(ExtractedBlueprint.template_id == template.id).order_by(ExtractedBlueprint.id.desc()).first()
    if not ext_bp:
        raise HTTPException(status_code=404, detail="Blueprint not found.")

    data = json.loads(ext_bp.canonical_blueprint_json)
    json_bytes = json.dumps(data, indent=2).encode('utf-8')
    filename = f"blueprint_{template.name.replace(' ', '_')}_v{template.version}.json"

    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/{template_id}/versions")
def list_template_versions(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    List all historical versions of a question paper template.
    """
    template = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    versions = db.query(TemplateVersion).filter(TemplateVersion.template_id == template_id).order_by(TemplateVersion.version_number.desc()).all()
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "change_summary": v.change_summary,
            "changed_by": v.changed_by.full_name if v.changed_by else "Faculty",
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "has_blueprint": bool(v.blueprint_json)
        }
        for v in versions
    ]


@router.post("/{template_id}/revert/{version_number}")
def revert_template_version(
    template_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty)
):
    """
    Revert template blueprint and parameters to a prior saved version.
    """
    template = db.query(QuestionPaperTemplate).filter(QuestionPaperTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    target_ver = db.query(TemplateVersion).filter(
        TemplateVersion.template_id == template_id,
        TemplateVersion.version_number == version_number
    ).first()
    if not target_ver:
        raise HTTPException(status_code=404, detail=f"Version {version_number} not found.")

    # Authorization Check
    if current_user.role != "admin" and template.owner_id and template.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to modify this template.")

    # Apply blueprint from target version
    bp_dict = json.loads(target_ver.blueprint_json)
    val_res = validate_extracted_blueprint(bp_dict)

    template.version += 1
    template.updated_at = datetime.datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.datetime.utcnow()

    ext_bp = db.query(ExtractedBlueprint).filter(ExtractedBlueprint.template_id == template.id).order_by(ExtractedBlueprint.id.desc()).first()
    if ext_bp:
        ext_bp.canonical_blueprint_json = target_ver.blueprint_json
        ext_bp.extraction_status = "faculty_corrected"
        ext_bp.validation_errors_json = json.dumps(val_res["errors"])
        ext_bp.validation_warnings_json = json.dumps(val_res["warnings"])

    # Log new version indicating reversion
    new_ver = TemplateVersion(
        template_id=template.id,
        version_number=template.version,
        blueprint_json=target_ver.blueprint_json,
        stored_filename=target_ver.stored_filename or template.stored_filename,
        changed_by_id=current_user.id,
        change_summary=f"Reverted to Version {version_number}"
    )
    db.add(new_ver)
    db.commit()

    return {
        "message": f"Successfully reverted template '{template.name}' to version {version_number}. New version is {template.version}.",
        "version": template.version,
        "blueprint": bp_dict
    }
