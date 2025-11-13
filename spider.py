import json  # 新增：用于格式化JSON输出
import time
import requests
import models
import datetime
from sqlalchemy import and_

# 起始日期：数字格式，代表2025年10月1日（格式：YYYYMMDD）
start = 20251001
# 循环67次（range(1,68) → 1到67），获取从起始日期后1天到67天的连续数据
for i in range(1, 68):
    # 分隔线：区分每次日期采集的输出，增强可读性
    print("=" * 60)
    try:
        # 日期计算逻辑
        start_date = datetime.datetime.strptime(str(start), '%Y%m%d')
        dates = (start_date + datetime.timedelta(days=i)).strftime('%Y%m%d')
        time_date = f"{dates}00"  # 简化字符串拼接
        url = f"http://www.nmc.cn/dataservice/real_map/rain/hour24/{time_date}"

        # 1. 打印当前采集的核心信息（清晰标注字段）
        print(f"【采集任务信息】")
        print(f"  序号：第{i:02d}次采集")  # 序号补零，格式统一
        print(f"  目标日期：{dates}（YYYYMMDD）")
        print(f"  时间标识：{time_date}（YYYYMMDDHH）")
        print(f"  请求URL：{url}")
        print("-" * 40)  # 子分隔线

        # 请求头：保持原逻辑，将bytes类型改为str（避免输出乱码，requests支持str headers）
        headers = {
            'accept': 'application/json,*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9,ja;q=0.8,ru;q=0.7',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Cookie': '__nmcu=1571015998256058368; __utrace=2ac6f32d764dcb4707a9abb6311b6bd0; ray_leech_token=1675698139',
            'Host': 'www.nmc.cn',
            'Pragma': 'no-cache',
            'Referer': 'http://www.nmc.cn/publish/observations/24hour-precipitation.html',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }

        # 2. 发送请求并打印响应状态
        print(f"【请求状态】")
        try:
            h = requests.get(url=url, headers=headers, timeout=10)  # 新增超时，避免卡壳
            h.raise_for_status()  # 触发HTTP错误（如404、500）
            print(f"  请求成功：HTTP {h.status_code}")

            # 格式化打印JSON响应（缩进2格，中文不转义）
            print(f"\n【接口返回JSON数据】")
            json_data = h.json()
            print(json.dumps(json_data, indent=2, ensure_ascii=False))
            print("-" * 40)

        except requests.exceptions.RequestException as e:
            print(f"  请求失败：{str(e)}")
            print(f"  跳过当前日期：{dates}")
            time.sleep(2)
            continue  # 跳过后续逻辑，进入下一次循环

        # 3. 解析数据并写入数据库（打印详细处理日志）
        print(f"【数据解析与入库】")
        try:
            # 提取核心数据列表（增加键存在判断，避免KeyError）
            if 'data' not in json_data or 'data' not in json_data['data']:
                print(f"  数据格式错误：响应中无 'data.data' 字段")
                time.sleep(2)
                continue

            rain_data_list = json_data['data']['data']
            print(f"  待处理数据条数：{len(rain_data_list)}条")

            for idx, resu in enumerate(rain_data_list, 1):  # 带序号，方便定位
                # 验证单条数据长度（确保字段完整）
                if len(resu) < 6:
                    print(f"  跳过无效数据（第{idx}条）：字段不足，数据：{resu}")
                    continue

                # 清晰打印单条数据的字段映射
                print(f"\n  处理第{idx}条数据：")
                print(f"    省份（pname）：{resu[0]}")
                print(f"    城市（name）：{resu[1]}")
                print(f"    城市编码（code）：{resu[2]}")
                print(f"    经度（lng）：{resu[3]}")
                print(f"    纬度（lat）：{resu[4]}")
                print(f"    24h降雨量（value）：{resu[5]}mm")
                print(f"    数据时间（datetiems）：{time_date}")

                # 数据库去重判断（用first()替代all()，效率更高）
                exists = models.XinXi.query.filter(
                    and_(
                        models.XinXi.datetiems == time_date,
                        models.XinXi.name == resu[1]
                    )
                ).first()

                if exists:
                    print(f"    状态：已存在，跳过入库")
                else:
                    # 写入数据库
                    new_rain_data = models.XinXi(
                        pname=resu[0],
                        name=resu[1],
                        code=resu[2],
                        lng=resu[3],
                        lat=resu[4],
                        value=resu[5],
                        datetiems=time_date
                    )
                    models.db.session.add(new_rain_data)
                    models.db.session.commit()
                    print(f"    状态：写入成功")

            print(f"\n  当前日期数据处理完成：{dates}")

        except Exception as e:
            models.db.session.rollback()  # 异常时回滚事务
            print(f"  数据处理异常：{str(e)}")

    except Exception as e:
        print(f"【采集流程异常】：{str(e)}")

    # 每次采集后休眠，避免请求过于频繁
    print("=" * 60 + "\n")
    time.sleep(2)

print("所有日期采集任务结束！")


