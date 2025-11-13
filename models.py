import flask
from flask_sqlalchemy import SQLAlchemy
import datetime
import os
from sqlalchemy import or_, and_
from flask_babelex import Babel
from flask_security import Security, SQLAlchemySessionUserDatastore, \
    UserMixin, RoleMixin, login_required, auth_token_required, http_auth_required
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

app = flask.Flask(__name__)
babel = Babel(app)  # 修正拼写错误
app.config['BABEL_DEFAULT_LOCALE'] = 'zh_CN'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = False
app.config['SECRET_KEY'] = 'kyes'

# 配置目标数据库（MySQL）- 请修改为你的实际信息
host = '127.0.0.1'  # MySQL主机地址
user = 'root'  # MySQL用户名
password = 'ming'  # 替换为你的实际密码
database = 'boss'  # 目标数据库名（已创建）
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{user}:{password}@{host}:3306/{database}"

# 源数据库路径（SQLite的.db文件）
SQLITE_DB_PATH = os.path.join(app.root_path, 'jiangshui.db')

app.config['SECURITY_PASSWORD_SALT'] = '123456789'
app.config['SECURITY_PASSWORD_HASH'] = 'sha512_crypt'

db = SQLAlchemy(app)


# 模型定义
class RolesUsers(db.Model):
    __tablename__ = 'roles_users'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column('user_id', db.Integer, db.ForeignKey('user.id'))
    role_id = db.Column('role_id', db.Integer, db.ForeignKey('role.id'))

    def __repr__(self):
        return "<{} 用户 {} 权限>".format(self.user_id, self.role_id)


class Role(db.Model, RoleMixin):
    __tablename__ = 'role'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __repr__(self):
        return "<{} 权限>".format(self.name)


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, unique=True, primary_key=True)
    username = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    last_login_at = db.Column(db.DateTime())
    current_login_at = db.Column(db.DateTime())
    last_login_ip = db.Column(db.String(100))
    current_login_ip = db.Column(db.String(100))
    login_count = db.Column(db.Integer)
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary='roles_users',
                            backref=db.backref('user', lazy='dynamic'))

    def __repr__(self):
        return "<{} 用户>".format(self.username)


class XinXi(db.Model):
    __tablename__ = 'xinxi'

    id = db.Column(db.Integer, unique=True, primary_key=True)
    pname = db.Column(db.String(255), name='省份', default='')
    name = db.Column(db.String(255), name='城市', default='')
    code = db.Column(db.Float, name='code', default=0)
    lng = db.Column(db.Float, name='lng', default=0)
    lat = db.Column(db.Float, name='lat', default=0)
    value = db.Column(db.Float, name='降雨量', default=0)
    datetiems = db.Column(db.String(255), name='日期', default='')
    date = db.Column(db.DateTime(), nullable=True, default=datetime.datetime.now)

    def __repr__(self):
        return "<{} 数据>".format(self.pname)


# 数据迁移函数（解决外键冲突版本）
def migrate_data():
    # 连接SQLite源数据库
    try:
        sqlite_engine = create_engine(f'sqlite:///{SQLITE_DB_PATH}')
        SQLiteSession = sessionmaker(bind=sqlite_engine)
        sqlite_session = SQLiteSession()
        print(f"成功连接SQLite源数据库：{SQLITE_DB_PATH}")
    except Exception as e:
        print(f"连接SQLite失败：{str(e)}")
        return

    # 连接MySQL目标数据库
    mysql_session = db.session

    try:
        # 1. 迁移XinXi表（无外键，先迁移）
        print("开始迁移xinxi表数据...")
        sqlite_xinxi = sqlite_session.query(XinXi).all()
        for item in sqlite_xinxi:
            mysql_item = XinXi(
                id=item.id,
                pname=item.pname,
                name=item.name,
                code=item.code,
                lng=item.lng,
                lat=item.lat,
                value=item.value,
                datetiems=item.datetiems,
                date=item.date
            )
            mysql_session.add(mysql_item)
        mysql_session.commit()  # 提交xinxi表数据
        print(f"xinxi表迁移完成，共{len(sqlite_xinxi)}条数据")

        # 2. 迁移Role表（主表，先迁移）
        print("开始迁移role表数据...")
        sqlite_roles = sqlite_session.query(Role).all()
        for role in sqlite_roles:
            mysql_role = Role(
                id=role.id,
                name=role.name,
                description=role.description
            )
            mysql_session.add(mysql_role)
        mysql_session.commit()  # 提交role表数据
        print(f"role表迁移完成，共{len(sqlite_roles)}条数据")

        # 3. 迁移User表（主表，再迁移）
        print("开始迁移user表数据...")
        sqlite_users = sqlite_session.query(User).all()
        for user in sqlite_users:
            mysql_user = User(
                id=user.id,
                username=user.username,
                email=user.email,
                password=user.password,
                last_login_at=user.last_login_at,
                current_login_at=user.current_login_at,
                last_login_ip=user.last_login_ip,
                current_login_ip=user.current_login_ip,
                login_count=user.login_count,
                active=user.active,
                confirmed_at=user.confirmed_at
            )
            mysql_session.add(mysql_user)
        mysql_session.commit()  # 提交user表数据（关键：确保外键存在）
        print(f"user表迁移完成，共{len(sqlite_users)}条数据")

        # 4. 迁移RolesUsers关联表（依赖user和role，最后迁移）
        print("开始迁移roles_users表数据...")
        sqlite_roles_users = sqlite_session.query(RolesUsers).all()
        valid_count = 0  # 记录有效迁移的关联记录数
        for ru in sqlite_roles_users:
            # 校验关联的用户和角色是否存在
            user_exists = mysql_session.query(User).filter_by(id=ru.user_id).first()
            role_exists = mysql_session.query(Role).filter_by(id=ru.role_id).first()

            if user_exists and role_exists:
                mysql_ru = RolesUsers(
                    id=ru.id,
                    user_id=ru.user_id,
                    role_id=ru.role_id
                )
                mysql_session.add(mysql_ru)
                valid_count += 1
            else:
                print(
                    f"跳过无效关联：user_id={ru.user_id}（{'存在' if user_exists else '不存在'}），role_id={ru.role_id}（{'存在' if role_exists else '不存在'}）")

        mysql_session.commit()  # 提交关联表数据
        print(f"roles_users表迁移完成，共{valid_count}/{len(sqlite_roles_users)}条有效数据")

        print("\n" + "=" * 50)
        print("所有数据迁移成功！")

    except Exception as e:
        mysql_session.rollback()  # 迁移失败时回滚
        print(f"\n迁移失败：{str(e)}")
    finally:
        sqlite_session.close()
        mysql_session.close()


if __name__ == '__main__':
    # 1. 在MySQL中创建表结构
    db.create_all()
    print("MySQL数据库表结构创建完成")

    # 2. 执行数据迁移（从SQLite到MySQL）
    migrate_data()

    # 3. 迁移完成后可启动服务（可选）
    # app.run(debug=True)