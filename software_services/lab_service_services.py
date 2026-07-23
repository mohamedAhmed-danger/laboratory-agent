"""
software_services/lab_service_services.py
"""

from models.models import LabService, db
from software_services.laboratory_services import LaboratoryService


class LabServiceService:

    # ── list / search ─────────────────────────────────────────────────────────

    @staticmethod
    def get_all_labs(page=1, per_page=10, search=None):
        query = LabService.query

        if search:
            query = query.filter(
                db.or_(
                    LabService.name.ilike(f'%{search}%'),
                    LabService.specimen.ilike(f'%{search}%'),
                )
            )

        query = query.order_by(LabService.name.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination, "تم العثور على التحاليل"

    # ── single ────────────────────────────────────────────────────────────────

    @staticmethod
    def get_lab_by_id(lab_id):
        lab = db.session.get(LabService, lab_id)
        if not lab:
            return None, "التحليل غير موجود"
        return lab, "تم العثور على التحليل"

    # ── create ────────────────────────────────────────────────────────────────

    @staticmethod
    def create_lab(name, price, laboratory_id=None, specimen=None,
                    durations=None, patient_instructions=None):
        if not name or not name.strip():
            return None, "اسم التحليل مطلوب"
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None, "السعر غير صحيح"

        if laboratory_id is None:
            try:
                laboratory_id = LaboratoryService.get_current_laboratory_id()
            except ValueError as e:
                return None, str(e)

        try:
            lab = LabService(
                laboratory_id=laboratory_id,
                name=name.strip(),
                price=price,
                specimen=(specimen or "").strip() or None,
                durations=(durations or "").strip() or None,
                patient_instructions=(patient_instructions or "").strip() or None,
                # description / keywords / alias_names / search_text are left
                # empty here on purpose — they'll be filled by the AI pipeline later.
            )
            db.session.add(lab)
            db.session.commit()
            return lab, "تم إنشاء التحليل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء إنشاء التحليل: {str(e)}"

    # ── update ────────────────────────────────────────────────────────────────

    @staticmethod
    def update_lab(lab_id, name=None, price=None, specimen=None,
                    durations=None, patient_instructions=None):
        lab = db.session.get(LabService, lab_id)
        if not lab:
            return None, "التحليل غير موجود"

        if name is not None:
            lab.name = name.strip()
        if price is not None:
            try:
                lab.price = float(price)
            except (TypeError, ValueError):
                return None, "السعر غير صحيح"
        if specimen is not None:
            lab.specimen = specimen.strip() or None
        if durations is not None:
            lab.durations = durations.strip() or None
        if patient_instructions is not None:
            lab.patient_instructions = patient_instructions.strip() or None
        # NOTE: description/keywords/alias_names/search_text are intentionally
        # NOT editable here — they belong to the AI knowledge pipeline (Phase 2).

        try:
            db.session.commit()
            return lab, "تم تحديث التحليل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء التحديث: {str(e)}"

    # ── delete ────────────────────────────────────────────────────────────────

    @staticmethod
    def delete_lab(lab_id):
        lab = db.session.get(LabService, lab_id)
        if not lab:
            return None, "التحليل غير موجود"
        try:
            db.session.delete(lab)
            db.session.commit()
            return lab, "تم حذف التحليل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء الحذف: {str(e)}"

    # ── used elsewhere (e.g. inquiry review dropdown) ───────────────────────────

    @staticmethod
    def get_all_labs_flat():
        """Unpaginated list — used where a full dropdown of labs is needed."""
        return LabService.query.order_by(LabService.name.asc()).all(), "تم العثور على التحاليل"