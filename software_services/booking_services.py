"""
software_services/booking_service.py
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from models.models import Booking, Status, db


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class BookingResult:
    success: bool
    booking: object
    message: str


# ── service ───────────────────────────────────────────────────────────────────

class BookingService:

    # ── list / search ─────────────────────────────────────────────────────────

    @staticmethod
    def get_all_bookings(page=1, per_page=10, search=None, status=None):
        query = Booking.query

        if search:
            query = query.filter(
                db.or_(
                    Booking.name.ilike(f'%{search}%'),
                    Booking.phone_number.ilike(f'%{search}%'),
                    Booking.reference_id.ilike(f'%{search}%'),
                )
            )

        if status:
            try:
                query = query.filter(Booking.status == Status(status))
            except ValueError:
                pass

        query = query.order_by(Booking.booking_time.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination, "تم العثور على الحجوزات"

    # ── single ────────────────────────────────────────────────────────────────

    @staticmethod
    def get_booking_by_id(booking_id):
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return None, "الحجز غير موجود"
        return booking, "تم العثور على الحجز"

    @staticmethod
    def get_booking_by_reference(reference_id):
        booking = Booking.query.filter_by(reference_id=reference_id).first()
        if not booking:
            return None, "الحجز غير موجود"
        return booking, "تم العثور على الحجز"

    # ── create ────────────────────────────────────────────────────────────────

    @staticmethod
    def create_booking(name, phone_number, date=None, details=None, comes_from=None):
        if not name or not name.strip():
            return BookingResult(False, None, "اسم المريض مطلوب")
        if not phone_number or not phone_number.strip():
            return BookingResult(False, None, "رقم الهاتف مطلوب")
        reference_id = uuid.uuid4().hex[:12].upper()

        try:
            booking = Booking(
                reference_id=reference_id,
                name=name.strip(),
                phone_number=phone_number.strip(),
                date=date,
                details=details,
                comes_from=comes_from,
                status=Status.PENDING,
                booking_time=datetime.now(timezone.utc),
            )
            db.session.add(booking)
            db.session.commit()
            return BookingResult(True, booking, "تم إنشاء الحجز بنجاح")
        except Exception as e:
            db.session.rollback()
            from sqlalchemy.exc import IntegrityError
            if isinstance(e, IntegrityError):
                # Fallback in the extremely rare case of reference_id collision
                reference_id = uuid.uuid4().hex[:12].upper()
                try:
                    booking = Booking(
                        reference_id=reference_id,
                        name=name.strip(),
                        phone_number=phone_number.strip(),
                        date=date,
                        details=details,
                        comes_from=comes_from,
                        status=Status.PENDING,
                        booking_time=datetime.now(timezone.utc),
                    )
                    db.session.add(booking)
                    db.session.commit()
                    return BookingResult(True, booking, "تم إنشاء الحجز بنجاح")
                except Exception as ex:
                    db.session.rollback()
                    return BookingResult(False, None, f"حدث خطأ أثناء إنشاء الحجز: {str(ex)}")
            return BookingResult(False, None, f"حدث خطأ أثناء إنشاء الحجز: {str(e)}")

    # ── update ────────────────────────────────────────────────────────────────

    @staticmethod
    def update_booking(booking_id, name=None, phone_number=None, date=None, details=None):
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return BookingResult(False, None, "الحجز غير موجود")

        if name is not None:
            booking.name = name.strip()
        if phone_number is not None:
            booking.phone_number = phone_number.strip()
        if date is not None:
            booking.date = date
        if details is not None:
            booking.details = details

        try:
            db.session.commit()
            return BookingResult(True, booking, "تم تحديث الحجز بنجاح")
        except Exception as e:
            db.session.rollback()
            return BookingResult(False, None, f"حدث خطأ أثناء تحديث الحجز: {str(e)}")

    # ── status ────────────────────────────────────────────────────────────────

    @staticmethod
    def update_status(booking_id, new_status: str):
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return BookingResult(False, None, "الحجز غير موجود")

        try:
            booking.status = Status(new_status)
            db.session.commit()
            return BookingResult(True, booking, "تم تحديث الحالة بنجاح")
        except ValueError:
            return BookingResult(False, None, "حالة غير صحيحة")
        except Exception as e:
            db.session.rollback()
            return BookingResult(False, None, f"حدث خطأ: {str(e)}")

    # ── delete ────────────────────────────────────────────────────────────────

    @staticmethod
    def delete_booking(booking_id):
        booking = db.session.get(Booking, booking_id)
        if not booking:
            return BookingResult(False, None, "الحجز غير موجود")

        try:
            db.session.delete(booking)
            db.session.commit()
            return BookingResult(True, booking, "تم حذف الحجز بنجاح")
        except Exception as e:
            db.session.rollback()
            return BookingResult(False, None, f"حدث خطأ أثناء الحذف: {str(e)}")

    # ── stats (for dashboard) ─────────────────────────────────────────────────

    @staticmethod
    def get_stats():
        total      = Booking.query.count()
        pending    = Booking.query.filter_by(status=Status.PENDING).count()
        attended   = Booking.query.filter_by(status=Status.ATTENDED).count()
        no_show    = Booking.query.filter_by(status=Status.NO_SHOW).count()
        return {
            "total":    total,
            "pending":  pending,
            "attended": attended,
            "no_show":  no_show,
        }