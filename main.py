# !/usr/bin/env python
# _*_ coding: utf-8 _*_
from flask import Flask, request, render_template,jsonify,abort,session,redirect, url_for
import os
import models
from models import app
import time
from sqlalchemy import or_,and_
from flask_security import Security, SQLAlchemySessionUserDatastore, \
    UserMixin, RoleMixin, login_required, auth_token_required, http_auth_required,current_user
import datetime


from prophet import Prophet
# from fbprophet import Prophet

import pandas as pd

from datetime import datetime  # 确保导入datetime模块（处理日期）



user_datastore = SQLAlchemySessionUserDatastore(models.db.session, models.User, models.Role)
security = Security(app, user_datastore)


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    stu_id = current_user.is_anonymous
    if stu_id:
        return redirect(url_for('logins'))
    if request.method == 'GET':
        results = models.XinXi.query.all()[::-1]
        Search = request.args.get('Search','')
        if Search:
            results = models.XinXi.query.filter(or_(models.XinXi.datetiems==Search,models.XinXi.pname==Search)).all()[::-1]
        return render_template('fenxi/table.html',**locals())


from datetime import datetime  # 确保导入datetime模块（处理日期）

from datetime import datetime  # 导入datetime处理日期


@app.route('/fenxi', methods=['GET', 'POST'])
def fenxi():
    stu_id = current_user.is_anonymous
    if stu_id:
        return redirect(url_for('logins'))

    if request.method == 'GET':
        # 城市列表处理（保持不变）
        citys = list(set([i.pname for i in models.XinXi.query.all()]))
        citys.sort()
        city = request.args.get('city')
        if not city:
            city = '北京'

        # 筛选当前城市的所有数据
        datas1 = models.XinXi.query.filter(models.XinXi.pname == city)

        # 折线图数据：按原始日期（含小时）去重，展示每日/每小时降雨量
        count_AQI = []  # 降雨量
        count_name = []  # 日期（格式：2023020200，去重后）
        for resu in datas1:
            if resu.datetiems not in count_name:
                count_name.append(resu.datetiems)
                count_AQI.append(resu.value)

        # 柱状图数据：按月聚合降水总量（核心适配新日期格式）
        monthly_rain_total = {}  # 存储“年月→月度总量”（如"2023-02"→120）
        for resu in datas1:
            try:
                # 解析日期：适配格式YYYYMMDDHH（如2023020200）
                date_obj = datetime.strptime(resu.datetiems, '%Y%m%d%H')
                # 提取“年月”作为聚合key（忽略小时，按月份合并）
                month_key = date_obj.strftime('%Y-%m')  # 格式：2023-02

                # 累加当月降雨量（同一月份的所有数据求和）
                if month_key in monthly_rain_total:
                    monthly_rain_total[month_key] += resu.value
                else:
                    monthly_rain_total[month_key] = resu.value
            except Exception as e:
                print(f"日期解析失败（格式应为YYYYMMDDHH）：{e}，跳过该数据")
                continue

        # 整理柱状图数据（按时间顺序排序）
        zuijia_name = sorted(monthly_rain_total.keys())  # x轴：年月（如2023-02）
        zuijia_shuju = [monthly_rain_total[month] for month in zuijia_name]  # y轴：月度总量

        return render_template('fenxi/fenxi.html', **locals())


# 确保导入方式正确（两种方式选一种）
# 方式1：导入整个datetime模块（推荐，与代码用法匹配）
import datetime


from datetime import datetime  # 确保启用方式2的导入：只导入datetime类
from prophet import Prophet  # 确保Prophet导入正确
import pandas as pd  # 确保pandas导入

@app.route('/yuce', methods=['GET', 'POST'])
def yuce():
    stu_id = current_user.is_anonymous
    if stu_id:
        return redirect(url_for('logins'))
    if request.method == 'GET':
        citys = list(set([i.pname for i in models.XinXi.query.all()]))
        citys.sort()
        city = request.args.get('city')
        if not city:
            city = '北京'
        shujus = models.XinXi.query.filter(models.XinXi.pname == city)
        dicts = {
            'ds': [],
            'y': [],
            'cap': [],
            'floor': []
        }
        for resu in shujus:
            # 方式2导入适配：直接用datetime.strptime（无多余datetime.）
            a = datetime.strptime(resu.datetiems, '%Y%m%d')
            if a.strftime('%Y-%m') not in dicts['ds']:
                dicts['ds'].append(a.strftime('%Y%m%d'))
                dicts['y'].append(resu.value),
                dicts['cap'].append(500)
                dicts['floor'].append(0)

        print(dicts)
        df = pd.DataFrame.from_dict(dicts)

        # 拟合模型
        m = Prophet(growth='logistic')
        m.fit(df)

        # 核心修改1：periods=10，只预测未来10天（原30天）
        future = m.make_future_dataframe(periods=10)
        future['cap'] = 500
        future['floor'] = 0

        # 预测数据集
        forecast = m.predict(future)
        data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
        dicts = data.to_dict(orient="list")
        datas = []
        for i in range(len(dicts['ds'])):
            dicts1 = {}
            dicts1['yhat'] = max(0, dicts['yhat'][i])  # 确保预测结果≥0
            dicts1['yhat_lower'] = max(0, dicts['yhat_lower'][i])
            dicts1['yhat_upper'] = max(0, round(dicts['yhat_upper'][i], 2))
            dicts1['ds'] = dicts['ds'][i].strftime("%Y-%m-%d")
            if round(dicts['yhat_upper'][i], 2) > 8:
                dicts1['yj'] = True
            else:
                dicts1['yj'] = False
            datas.append(dicts1)

        # 核心修改2：只取最后10条数据（即未来10天预测结果），原35条
        # 核心修改：去掉[::-1]逆序，保留未来10天的原始时间顺序（日期由小到大）
        datas = datas[-10:]
        print(datas)


        return render_template('fenxi/yuce.html',** locals())





@app.route('/signups', methods=['GET', 'POST'])
def signup():
    uuid = current_user.is_anonymous
    if request.method == 'POST':
        user = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('pwd')
        if models.User.query.filter(models.User.username == user).all():
            return render_template('user/index.html', error='账号名已被注册')
        elif user == '' or password == '' or email == '':
            return render_template('user/index.html', error='输入不能为空')
        else:
            new_user = user_datastore.create_user(username=user,email=email, password=password)
            normal_role = user_datastore.find_role('User')
            models.db.session.add(new_user)
            user_datastore.add_role_to_user(new_user, normal_role)
            models.db.session.commit()
            login_user(new_user, remember=True)
            return redirect(url_for('index'))


from flask_security.utils import login_user, logout_user
@app.route('/logins', methods=['GET', 'POST'])
def logins():
    uuid = current_user.is_anonymous
    if not uuid:
        return redirect(url_for('index'))
    if request.method=='GET':
        return render_template('user/index.html')
    elif request.method=='POST':
        user = request.form.get('name')
        password = request.form.get('pwd')
        data = models.User.query.filter(and_(models.User.username==user,models.User.password==password)).first()
        if not data:
            return render_template('user/index.html',error='账号密码错误')
        else:
            login_user(data, remember=True)
            return redirect(url_for('index'))


@app.route('/logins_admin', methods=['GET', 'POST'])
def logins_admin():
    uuid = current_user.is_anonymous
    if not uuid:
        return redirect(url_for('index'))
    if request.method=='GET':
        return render_template('user/admin.html')
    elif request.method=='POST':
        user = request.form.get('name')
        password = request.form.get('pwd')
        data = models.User.query.filter(and_(models.User.username==user,models.User.password==password)).first()
        if not data:
            return render_template('user/admin.html',error='账号密码错误')
        bool = False
        for resu in data.roles:
            if resu.name == 'admin':
                bool = True
        if bool:
            login_user(data, remember=True)
            return redirect('/admin')
        else:
            return render_template('user/admin.html', error='账号无权限')



@app.route('/loginsout', methods=['GET'])
def loginsout():
    if request.method=='GET':
        logout_user()
        return redirect(url_for('logins'))




