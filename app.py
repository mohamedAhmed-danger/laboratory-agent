import os
from flask import Flask, render_template, request, redirect, url_for, flash,jsonify
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv

from models.models import db, User, Laboratory
from software_services.laboratory_services import LaboratoryService
from software_services.service_services import ServiceService
from software_services.booking_services import BookingService
from models.models import Status
from software_services.inquiry_services import InquiryService
from software_services.complaint_services import ComplaintService
from software_services.user_services import UserService


# Load environment variables
load_dotenv()

# ── App & Config ──────────────────────────────────────────────────────────────

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-unsafe-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///laboratory.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── Extensions ────────────────────────────────────────────────────────────────

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يجب تسجيل الدخول أولاً'
login_manager.login_message_category = 'error'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ── Context Processor (sidebar badge) ────────────────────────────────────────

@app.context_processor
def inject_globals():
    from models.models import Inquiry, Status
    try:
        pending_count = Inquiry.query.filter_by(status=Status.PENDING).count()
    except Exception:
        pending_count = 0
    return dict(pending_inquiries_count=pending_count)

# ── Auth Routes ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')




@app.route('/users')
@login_required
def users():
    all_users = UserService.get_all_users()
    return render_template('users.html', users=all_users)


@app.route('/users/new', methods=['GET', 'POST'])
@login_required
def create_user():
    if request.method == 'POST':
        name     = request.form['name']
        password = request.form['password']
        user, message = UserService.create_user(name, password)
        if user:
            flash(message, 'success')
            return redirect(url_for('users'))
        else:
            flash(message, 'danger')

    return render_template('create_user.html')


@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user, message = UserService.get_user_by_id(user_id)

    if not user:
        flash(message, 'danger')
        return redirect(url_for('users'))

    if request.method == 'POST':
        name     = request.form['name']
        password = request.form['password']
        updated_user, message = UserService.update_user(user_id, name, password)

        if updated_user:
            flash(message, 'success')
            return redirect(url_for('users'))
        else:
            flash(message, 'danger')

    return render_template('edit_user.html', user=user)


# ── Laboratory Routes ─────────────────────────────────────────────────────────

@app.route('/laboratory')
@login_required
def laboratory_settings():
    lab, msg = LaboratoryService.get_laboratory()
    return render_template('laboratory/settings.html', lab=lab)

@app.route('/laboratory/update', methods=['POST'])
@login_required
def laboratory_update():
    name    = request.form.get('name')
    address = request.form.get('address')
    info    = request.form.get('info')

    lab = Laboratory.query.first()

    if lab:
        updated, msg = LaboratoryService.update_laboratory(name=name, address=address, info=info)
    else:
        updated, msg = LaboratoryService.create_initial_laboratory(name=name, address=address, info=info)

    if updated:
        flash(msg, 'success')
    else:
        flash(msg, 'error')

    return redirect(url_for('laboratory_settings'))


"""
Add these routes to your app.py
Import at top: from software_services.service_service import ServiceService
"""

# ── Services Routes ───────────────────────────────────────────────────────────

@app.route('/services')
@login_required
def list_services():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip() or None

    pagination, msg = ServiceService.get_all_services(
        page=page,
        per_page=10,
        search=search
    )

    if pagination is None:
        flash(msg, 'error')
        pagination = type('Pagination', (), {
            'items': [],
            'total': 0,
            'pages': 0,
            'page': 1,
            'has_prev': False,
            'has_next': False,
            'prev_num': 1,
            'next_num': 1
        })()

    return render_template(
        'services/list.html',
        services=pagination.items,
        pagination=pagination,
        search=search
    )


@app.route('/services/create', methods=['GET', 'POST'])
@login_required
def create_service():
    if request.method == 'POST':
        name        = request.form.get('name')
        price       = request.form.get('price')
        description = request.form.get('description')

        service, msg = ServiceService.create_service(
            name=name, price=price, description=description
        )
        if service:
            flash(msg, 'success')
            return redirect(url_for('list_services'))
        flash(msg, 'error')

    return render_template('services/create.html', service=None)


@app.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_service(service_id):
    service, msg = ServiceService.get_service_by_id(service_id)
    if not service:
        flash(msg, 'error')
        return redirect(url_for('list_services'))

    if request.method == 'POST':
        name        = request.form.get('name')
        price       = request.form.get('price')
        description = request.form.get('description')

        updated, msg = ServiceService.update_service(
            service_id=service_id, name=name, price=price, description=description
        )
        if updated:
            flash(msg, 'success')
            return redirect(url_for('list_services'))
        flash(msg, 'error')

    return render_template('services/edit.html', service=service)


@app.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
def delete_service(service_id):
    service, msg = ServiceService.delete_service(service_id)
    if service:
        flash(msg, 'success')
    else:
        flash(msg, 'error')
    return redirect(url_for('list_services'))
@app.route('/bookings')
@login_required
def list_bookings():
    page    = request.args.get('page', 1, type=int)
    search  = request.args.get('search', '').strip() or None
    status  = request.args.get('status', '').strip() or None
 
    pagination, _ = BookingService.get_all_bookings(
        page=page, per_page=10, search=search, status=status
    )
    stats = BookingService.get_stats()
 
    return render_template(
        'bookings/list.html',
        bookings=pagination.items,
        pagination=pagination,
        search=search,
        status_filter=status,
        stats=stats,
        all_statuses=Status,
    )
 
 
# ── detail ────────────────────────────────────────────────────────────────────
 
@app.route('/bookings/<int:booking_id>')
@login_required
def view_booking(booking_id):
    booking, msg = BookingService.get_booking_by_id(booking_id)
    if not booking:
        flash(msg, 'error')
        return redirect(url_for('list_bookings'))
    return render_template('bookings/detail.html', booking=booking, all_statuses=Status)
 
 
# ── create ────────────────────────────────────────────────────────────────────
 
@app.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def create_booking():
    if request.method == 'POST':
        result = BookingService.create_booking(
            name=request.form.get('name'),
            phone_number=request.form.get('phone_number'),
            date=request.form.get('date') or None,
            details=request.form.get('details') or None,
            comes_from='dashboard',
        )
        if result.success:
            flash(result.message, 'success')
            return redirect(url_for('list_bookings'))
        flash(result.message, 'error')
 
    return render_template('bookings/create.html')
 
 
# ── edit ──────────────────────────────────────────────────────────────────────
 
@app.route('/bookings/<int:booking_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_booking(booking_id):
    booking, msg = BookingService.get_booking_by_id(booking_id)
    if not booking:
        flash(msg, 'error')
        return redirect(url_for('list_bookings'))
 
    if request.method == 'POST':
        result = BookingService.update_booking(
            booking_id=booking_id,
            name=request.form.get('name'),
            phone_number=request.form.get('phone_number'),
            date=request.form.get('date') or None,
            details=request.form.get('details') or None,
        )
        if result.success:
            flash(result.message, 'success')
            return redirect(url_for('list_bookings'))
        flash(result.message, 'error')
 
    return render_template('bookings/edit.html', booking=booking)
 
 
# ── update status (AJAX) ──────────────────────────────────────────────────────
 
@app.route('/bookings/<int:booking_id>/status', methods=['POST'])
@login_required
def update_booking_status(booking_id):
    new_status = request.form.get('status') or request.json.get('status')
    result = BookingService.update_status(booking_id, new_status)
    if request.is_json:
        return jsonify(success=result.success, message=result.message)
    flash(result.message, 'success' if result.success else 'error')
    return redirect(url_for('list_bookings'))
 
 
# ── delete ────────────────────────────────────────────────────────────────────
 
@app.route('/bookings/<int:booking_id>/delete', methods=['POST'])
@login_required
def delete_booking(booking_id):
    result = BookingService.delete_booking(booking_id)
    flash(result.message, 'success' if result.success else 'error')
    return redirect(url_for('list_bookings'))



@app.route('/inquiries')
@login_required
def list_inquiries():
    page    = request.args.get('page', 1, type=int)
    search  = request.args.get('search', '').strip()
    status  = request.args.get('status', '')
 
    pagination, _ = InquiryService.get_all_inquiries(
        page=page, per_page=10, search=search or None, status=status or None
    )
    stats = InquiryService.get_stats()
 
    return render_template(
        'inquiries/list.html',
        inquiries=pagination.items,
        pagination=pagination,
        search=search,
        status=status,
        statuses=Status,
        stats=stats,
    )
 
 
@app.route('/inquiries/<int:inquiry_id>')
@login_required
def inquiry_detail(inquiry_id):
    result = InquiryService.get_inquiry_by_id(inquiry_id)
    if not result.success:
        flash(result.message, 'error')
        return redirect(url_for('list_inquiries'))
    return render_template('inquiries/detail.html', inquiry=result.inquiry)
 
 
@app.route('/inquiries/<int:inquiry_id>/status', methods=['POST'])
@login_required
def update_inquiry_status(inquiry_id):
    new_status = request.form.get('status')
    result = InquiryService.update_status(inquiry_id, new_status)
    flash(result.message, 'success' if result.success else 'error')
    return redirect(request.referrer or url_for('list_inquiries'))
 
 
@app.route('/inquiries/<int:inquiry_id>/delete', methods=['POST'])
@login_required
def delete_inquiry(inquiry_id):
    result = InquiryService.delete_inquiry(inquiry_id)
    flash(result.message, 'success' if result.success else 'error')
    return redirect(url_for('list_inquiries'))

@app.route('/complaints')
@login_required
def list_complaints():
    page   = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '')
 
    pagination, _ = ComplaintService.get_all_complaints(
        page=page, per_page=10, search=search or None, status=status or None
    )
    stats = ComplaintService.get_stats()
 
    return render_template(
        'complaints/list.html',
        complaints=pagination.items,
        pagination=pagination,
        search=search,
        status=status,
        statuses=Status,
        stats=stats,
    )
 
 
@app.route('/complaints/<int:complaint_id>')
@login_required
def complaint_detail(complaint_id):
    result = ComplaintService.get_complaint_by_id(complaint_id)
    if not result.success:
        flash(result.message, 'error')
        return redirect(url_for('list_complaints'))
    return render_template('complaints/detail.html', complaint=result.complaint)
 
 
@app.route('/complaints/<int:complaint_id>/status', methods=['POST'])
@login_required
def update_complaint_status(complaint_id):
    new_status = request.form.get('status')
    result = ComplaintService.update_status(complaint_id, new_status)
    flash(result.message, 'success' if result.success else 'error')
    return redirect(request.referrer or url_for('list_complaints'))
 
 
@app.route('/complaints/<int:complaint_id>/delete', methods=['POST'])
@login_required
def delete_complaint(complaint_id):
    result = ComplaintService.delete_complaint(complaint_id)
    flash(result.message, 'success' if result.success else 'error')
    return redirect(url_for('list_complaints'))


"""
Page & Client routes for app.py
"""

from software_services.page_services import PageService


@app.route('/pages')
@login_required
def list_pages():
    pages, msg = PageService.get_all_pages()
    return render_template('pages/list.html', pages=pages)


@app.route('/pages/create', methods=['GET', 'POST'])
@login_required
def create_page():
    platforms, _ = PageService.get_all_platforms()

    if request.method == 'POST':
        platform_id = request.form['platform_id']
        page_id = request.form['page_id']
        token = request.form['token']
        laboratory_id = 1  # single-lab setup

        page, msg = PageService.create_page(laboratory_id, platform_id, page_id, token)
        if page:
            flash(msg, 'success')
            return redirect(url_for('list_pages'))
        flash(msg, 'error')

    return render_template('pages/create.html', platforms=platforms)


@app.route('/pages/<int:platform_id>/<page_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_page(platform_id, page_id):
    page, msg = PageService.get_page(platform_id, page_id)
    if not page:
        flash(msg, 'error')
        return redirect(url_for('list_pages'))

    if request.method == 'POST':
        token = request.form['token']
        updated, msg = PageService.update_page_token(platform_id, page_id, token)
        if updated:
            flash(msg, 'success')
            return redirect(url_for('list_pages'))
        flash(msg, 'error')

    return render_template('pages/edit.html', page=page)


@app.route('/pages/<int:platform_id>/<page_id>/delete', methods=['POST'])
@login_required
def delete_page(platform_id, page_id):
    page, msg = PageService.delete_page(platform_id, page_id)
    flash(msg, 'success' if page else 'error')
    return redirect(url_for('list_pages'))


# ── Clients (scoped to a page) ───────────────────────────────────────────────

@app.route('/pages/<int:platform_id>/<page_id>/clients')
@login_required
def list_clients(platform_id, page_id):
    search = request.args.get('search', '')
    page_num = request.args.get('page', 1, type=int)

    page, _ = PageService.get_page(platform_id, page_id)
    clients, msg = PageService.get_clients_for_page(
        platform_id, page_id, search=search, page_num=page_num
    )
    return render_template(
        'pages/clients.html', page=page, clients=clients, search=search
    )


@app.route('/pages/<int:platform_id>/<page_id>/clients/<sender_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(platform_id, page_id, sender_id):
    client, msg = PageService.get_client(platform_id, page_id, sender_id)
    if not client:
        flash(msg, 'error')
        return redirect(url_for('list_clients', platform_id=platform_id, page_id=page_id))

    if request.method == 'POST':
        summary = request.form['summary']
        updated, msg = PageService.update_client_summary(platform_id, page_id, sender_id, summary)
        if updated:
            flash(msg, 'success')
            return redirect(url_for('list_clients', platform_id=platform_id, page_id=page_id))
        flash(msg, 'error')

    return render_template('pages/client_edit.html', client=client)


@app.route('/pages/<int:platform_id>/<page_id>/clients/<sender_id>/delete', methods=['POST'])
@login_required
def delete_client(platform_id, page_id, sender_id):
    client, msg = PageService.delete_client(platform_id, page_id, sender_id)
    flash(msg, 'success' if client else 'error')
    return redirect(url_for('list_clients', platform_id=platform_id, page_id=page_id))



from software_services.platform_services import PlatformService
 
 
@app.route('/platforms')
@login_required
def list_platforms():
    platforms, msg = PlatformService.get_all_platforms()
    return render_template('platforms/list.html', platforms=platforms)
 
 
@app.route('/platforms/create', methods=['GET', 'POST'])
@login_required
def create_platform():
    if request.method == 'POST':
        name = request.form['name']
        platform, msg = PlatformService.create_platform(name)
        if platform:
            flash(msg, 'success')
            return redirect(url_for('list_platforms'))
        flash(msg, 'error')
 
    return render_template('platforms/create.html')
 
 
@app.route('/platforms/<int:platform_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_platform(platform_id):
    platform, msg = PlatformService.get_platform_by_id(platform_id)
    if not platform:
        flash(msg, 'error')
        return redirect(url_for('list_platforms'))
 
    if request.method == 'POST':
        name = request.form['name']
        updated, msg = PlatformService.update_platform(platform_id, name)
        if updated:
            flash(msg, 'success')
            return redirect(url_for('list_platforms'))
        flash(msg, 'error')
 
    return render_template('platforms/edit.html', platform=platform)
# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Read debug setting from environment
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    app.run(debug=debug_mode)