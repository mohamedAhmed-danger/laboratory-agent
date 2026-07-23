"""
software_services/bundle_services.py
"""

from models.models import Bundle, BundleService, LabService, db
from sqlalchemy.orm import joinedload
from software_services.laboratory_services import LaboratoryService


class BundleServiceLogic:
    """Service layer for Bundle CRUD. Named BundleServiceLogic (not BundleService)
    to avoid clashing with models.BundleService, the join-table model.
    Import in app.py as:
        from software_services.bundle_services import BundleServiceLogic
    """

    # ── list / search ─────────────────────────────────────────────────────────

    @staticmethod
    def get_all_bundles(page=1, per_page=10, search=None):
        query = Bundle.query.options(
            joinedload(Bundle.services).joinedload(BundleService.service)
        )

        if search:
            query = query.filter(Bundle.name.ilike(f'%{search}%'))

        query = query.order_by(Bundle.name.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination, "تم العثور على الباقات"

    # ── single ────────────────────────────────────────────────────────────────

    @staticmethod
    def get_bundle_by_id(bundle_id):
        bundle = db.session.get(Bundle, bundle_id)
        if not bundle:
            return None, "الباقة غير موجودة"
        return bundle, "تم العثور على الباقة"

    # ── create ────────────────────────────────────────────────────────────────

    @staticmethod
    def create_bundle(name, price, laboratory_id=None, patient_instructions=None,
                       description=None, lab_ids=None):
        if not name or not name.strip():
            return None, "اسم الباقة مطلوب"
        try:
            price = float(price) if price not in (None, '') else None
        except (TypeError, ValueError):
            return None, "السعر غير صحيح"

        if laboratory_id is None:
            try:
                laboratory_id = LaboratoryService.get_current_laboratory_id()
            except ValueError as e:
                return None, str(e)

        try:
            bundle = Bundle(
                laboratory_id=laboratory_id,
                name=name.strip(),
                price=price,
                patient_instructions=(patient_instructions or "").strip() or None,
                description=(description or "").strip() or None,
            )
            db.session.add(bundle)
            db.session.flush()  # get bundle.id before commit

            for lab_id in (lab_ids or []):
                link = BundleService(bundle_id=bundle.id, service_id=int(lab_id))
                db.session.add(link)

            db.session.commit()
            return bundle, "تم إنشاء الباقة بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء إنشاء الباقة: {str(e)}"

    # ── update ────────────────────────────────────────────────────────────────

    @staticmethod
    def update_bundle(bundle_id, name=None, price=None, patient_instructions=None,
                       description=None, lab_ids=None):
        bundle = db.session.get(Bundle, bundle_id)
        if not bundle:
            return None, "الباقة غير موجودة"

        if name is not None:
            bundle.name = name.strip()
        if price is not None:
            try:
                bundle.price = float(price) if price != '' else None
            except (TypeError, ValueError):
                return None, "السعر غير صحيح"
        if patient_instructions is not None:
            bundle.patient_instructions = patient_instructions.strip() or None
        if description is not None:
            bundle.description = description.strip() or None

        try:
            if lab_ids is not None:
                # replace the set of linked labs entirely
                BundleService.query.filter_by(bundle_id=bundle_id).delete()
                for lab_id in lab_ids:
                    db.session.add(BundleService(bundle_id=bundle_id, service_id=int(lab_id)))

            db.session.commit()
            return bundle, "تم تحديث الباقة بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء التحديث: {str(e)}"

    # ── delete ────────────────────────────────────────────────────────────────

    @staticmethod
    def delete_bundle(bundle_id):
        bundle = db.session.get(Bundle, bundle_id)
        if not bundle:
            return None, "الباقة غير موجودة"
        try:
            db.session.delete(bundle)  # cascades to BundleService rows
            db.session.commit()
            return bundle, "تم حذف الباقة بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء الحذف: {str(e)}"

    # ── helper: labs available for the checkbox picker ──────────────────────────

    @staticmethod
    def get_all_labs_for_picker():
        return LabService.query.order_by(LabService.name.asc()).all()