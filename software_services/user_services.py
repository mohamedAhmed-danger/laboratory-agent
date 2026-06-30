from models.models import User, db


class UserService:

    # this function is used to create a new user in the database
    @staticmethod
    def create_user(name, password):
        name=name.strip().lower()
        existing_user= User.query.filter_by(username=name).first()
        if existing_user:
            return None, "اسم المستخدم موجود بالفعل"
        
        try:
            new_user = User(username=name, password=password)
            db.session.add(new_user)
            db.session.commit()
            return new_user, "تم إنشاء المستخدم بنجاح"
        except Exception as e:
            db.session.rollback()
            return None, f"حدث خطأ أثناء إنشاء المستخدم: {str(e)}"
           

        

    # update user with validation
    @staticmethod
    def update_user(user_id, name=None, password=None):
        user = User.query.get(user_id)

        if not user:
            return None, "المستخدم غير موجود"

        if name and name != user.username:
            the_user = User.query.filter_by(username=name).first()

            if the_user:
                return None, "اسم المستخدم موجود بالفعل"

            user.username = name

        if password:
            user.password = password
        try:
          db.session.commit()
          return user, "تم تحديث المستخدم بنجاح"
        except Exception as e:
          db.session.rollback()
          return None, f"حدث خطأ أثناء تحديث المستخدم: {str(e)}"
    # this function is used to login a user by checking the name and password
    @staticmethod
    def login_user(name, password):
        user = User.query.filter_by(username=name).first()

        if user and user.password == password:
            return user, "تم تسجيل الدخول بنجاح"
        else:
            return None, "اسم المستخدم أو كلمة المرور غير صحيحة"

    # this function is used to get a user by id
    @staticmethod
    def get_user_by_id(user_id):
        user = User.query.get(user_id)

        if user:
            return user, "تم العثور على المستخدم"
        else:
            return None, "المستخدم غير موجود"

    # this function is used to get all users in the database
    @staticmethod
    def get_all_users():
        users = User.query.all()

        return users
