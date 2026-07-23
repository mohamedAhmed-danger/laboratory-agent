from models.models import Laboratory, db

class LaboratoryService:

    @staticmethod
    def get_all_laboratories(page=1, per_page=10, search=None):
        """Get paginated list of laboratories with optional search."""
        query = Laboratory.query

        if search:
            query = query.filter(
                (Laboratory.name.ilike(f"%{search}%")) |
                (Laboratory.address.ilike(f"%{search}%"))
            )

        try:
            pagination = query.order_by(Laboratory.id.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            return pagination, "تم جلب معامل التحاليل بنجاح"
        except Exception as e:
            return None, f"حدث خطأ أثناء الجلب: {str(e)}"

    @staticmethod
    def get_laboratory_by_id(lab_id):
        """Get a single laboratory by ID."""
        lab = Laboratory.query.get(lab_id)
        if not lab:
            return None, "المعمل غير موجود"
        return lab, "تم العثور على المعمل"

    @staticmethod
    def create_laboratory(name, address=None, info=None):
        """Create a new laboratory."""
        if not name or not name.strip():
            return None, "اسم المعمل مطلوب"

        lab = Laboratory(
            name=name.strip(),
            address=address.strip() if address else None,
            info=info.strip() if info else None
        )
        try:
            db.session.add(lab)
            db.session.commit()
            return lab, "تم إضافة المعمل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء الإضافة: {str(e)}"

    @staticmethod
    def update_laboratory(lab_id, name=None, address=None, info=None):
        """Update an existing laboratory."""
        lab = Laboratory.query.get(lab_id)
        if not lab:
            return None, "المعمل غير موجود"

        if name:
            lab.name = name.strip()
        if address is not None:
            lab.address = address.strip() if address else None
        if info is not None:
            lab.info = info.strip() if info else None

        try:
            db.session.commit()
            return lab, "تم تحديث بيانات المعمل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء التحديث: {str(e)}"

    @staticmethod
    def delete_laboratory(lab_id):
        """Delete a laboratory."""
        lab = Laboratory.query.get(lab_id)
        if not lab:
            return None, "المعمل غير موجود"

        try:
            db.session.delete(lab)
            db.session.commit()
            return lab, "تم حذف المعمل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء الحذف: {str(e)}"