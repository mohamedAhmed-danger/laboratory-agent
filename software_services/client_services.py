"""
software_services/client_services.py
"""

from models.models import Client, db


class ClientService:

    # ── read ──────────────────────────────────────────────────────────────────

    @staticmethod
    def get_clients_for_page(platform_id, page_id, search=None, page_num=1, per_page=10):
        query = Client.query.filter_by(platform_id=platform_id, page_id=page_id)

        if search:
            query = query.filter(Client.sender_id.ilike(f'%{search}%'))

        query = query.order_by(Client.expiration_date.desc())
        pagination = query.paginate(page=page_num, per_page=per_page, error_out=False)
        return pagination, "تم العثور على العملاء"

    @staticmethod
    def get_client(platform_id, page_id, sender_id):
        client = Client.query.filter_by(
            platform_id=platform_id, page_id=page_id, sender_id=sender_id
        ).first()
        if not client:
            return None, "العميل غير موجود"
        return client, "تم العثور على العميل"

    # ── write ─────────────────────────────────────────────────────────────────

    @staticmethod
    def update_client_summary(platform_id, page_id, sender_id, summary):
        client = Client.query.filter_by(
            platform_id=platform_id, page_id=page_id, sender_id=sender_id
        ).first()
        if not client:
            return None, "العميل غير موجود"
        try:
            client.summary = summary
            db.session.commit()
            return client, "تم تحديث ملخص العميل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء التحديث: {str(e)}"

    @staticmethod
    def update_client_summary_and_last_bot_message(sender_id, page_id, platform_id, summary=None, last_bot_message=None):
        client = Client.query.filter_by(
            platform_id=platform_id, page_id=page_id, sender_id=sender_id
        ).first()

        if not client:
            client = Client(
                platform_id=platform_id,
                page_id=page_id,
                sender_id=sender_id,
                summary=summary,
                last_bot_message=last_bot_message
            )
            db.session.add(client)
        else:
            if summary is not None:
                client.summary = summary
            if last_bot_message is not None:
                client.last_bot_message = last_bot_message

        try:
            db.session.commit()
            return client, "تم حفظ حالة العميل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء حفظ حالة العميل: {str(e)}"

    @staticmethod
    def delete_client(platform_id, page_id, sender_id):
        client = Client.query.filter_by(
            platform_id=platform_id, page_id=page_id, sender_id=sender_id
        ).first()
        if not client:
            return None, "العميل غير موجود"
        try:
            db.session.delete(client)
            db.session.commit()
            return client, "تم حذف العميل بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء الحذف: {str(e)}"
