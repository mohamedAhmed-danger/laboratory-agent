"""
software_services/service_service.py
"""

from models.models import Service, Laboratory, db


class ServiceService:


    @staticmethod
    def get_all_services(page=1, per_page=10, search=None):
        try:
            query = Service.query

            if search:
                 query = query.filter(Service.name.ilike(f"%{search}%"))

            pagination = query.order_by(Service.id.desc()).paginate(
               page=page,
               per_page=per_page,
               error_out=False
            )

            return pagination, "Success"

        except Exception as e:
            return None, str(e)

    @staticmethod
    def get_service_by_id(service_id):
        service = db.session.get(Service, service_id)
        if not service:
            return None, "الخدمة غير موجودة"
        return service, "تم العثور على الخدمة"

    @staticmethod
    def create_service(name, price, description=None):
        lab = Laboratory.query.first()
        if not lab:
            return None, "لم يتم العثور على بيانات المختبر"

        name = name.strip()
        existing = Service.query.filter_by(name=name, laboratory_id=lab.id).first()
        if existing:
            return None, "توجد خدمة بنفس الاسم بالفعل"

        try:
            service = Service(
                laboratory_id=lab.id,
                name=name,
                description=description.strip() if description else None,
                price=float(price),
            )
            db.session.add(service)
            db.session.commit()
            return service, "تم إضافة الخدمة بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء الإضافة: {str(e)}"

    @staticmethod
    def update_service(service_id, name=None, price=None, description=None):
        service = db.session.get(Service, service_id)
        if not service:
            return None, "الخدمة غير موجودة"

        if name:
            name = name.strip()
            duplicate = Service.query.filter_by(
                name=name, laboratory_id=service.laboratory_id
            ).first()
            if duplicate and duplicate.id != service.id:
                return None, "توجد خدمة بنفس الاسم بالفعل"
            service.name = name

        if price is not None:
            service.price = float(price)

        if description is not None:
            service.description = description.strip()

        try:
            db.session.commit()
            return service, "تم تحديث الخدمة بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء التحديث: {str(e)}"

    @staticmethod
    def delete_service(service_id):
        service = db.session.get(Service, service_id)
        if not service:
            return None, "الخدمة غير موجودة"
        try:
            db.session.delete(service)
            db.session.commit()
            return service, "تم حذف الخدمة بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء الحذف: {str(e)}"