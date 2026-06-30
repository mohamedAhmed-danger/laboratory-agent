"""
software_services/laboratory_service.py
"""

from models.models import Laboratory, db


class LaboratoryService:

    @staticmethod
    def get_laboratory():
        """Get the single laboratory record."""
        lab = Laboratory.query.first()
        if not lab:
            return None, "لم يتم العثور على بيانات المختبر"
        return lab, "تم العثور على بيانات المختبر"

    @staticmethod
    def update_laboratory(name=None, address=None, info=None):
        """Update the laboratory's info."""
        lab = Laboratory.query.first()
        if not lab:
            return None, "لم يتم العثور على بيانات المختبر"

        if name:
            lab.name = name.strip()
        if address:
            lab.address = address.strip()
        if info:
            lab.info = info.strip()

        try:
            db.session.commit()
            return lab, "تم تحديث بيانات المختبر بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء التحديث: {str(e)}"

    @staticmethod
    def create_initial_laboratory(name, address, info):
        """Create the laboratory record if it doesn't exist yet (run once on setup)."""
        existing = Laboratory.query.first()
        if existing:
            return existing, "المختبر موجود بالفعل"

        lab = Laboratory(name=name, address=address, info=info)
        try:
            db.session.add(lab)
            db.session.commit()
            return lab, "تم إنشاء المختبر بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء الإنشاء: {str(e)}"