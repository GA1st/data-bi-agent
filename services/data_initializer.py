import random
from datetime import datetime, timedelta

from core.database import execute_update, execute_query

CATEGORIES = [
    ("电子产品", "手机、电脑、平板等电子设备"),
    ("办公用品", "文具、打印耗材、办公家具"),
    ("家居用品", "厨房用品、收纳、装饰品"),
    ("服装鞋帽", "男装、女装、童装、鞋类"),
    ("食品饮料", "零食、饮品、生鲜食品"),
    ("美妆个护", "护肤品、化妆品、洗护用品"),
    ("运动户外", "运动器材、户外装备、健身用品"),
    ("图书音像", "图书、电子书、音像制品"),
    ("母婴用品", "奶粉、纸尿裤、婴童玩具"),
    ("汽车配件", "车载电器、养护用品、配件"),
]

REGIONS = ["华东", "华南", "华北", "华中", "西南", "西北", "东北"]
CITIES = {
    "华东": ["上海", "南京", "杭州", "苏州", "宁波"],
    "华南": ["广州", "深圳", "东莞", "佛山", "厦门"],
    "华北": ["北京", "天津", "石家庄", "太原", "济南"],
    "华中": ["武汉", "长沙", "郑州", "合肥", "南昌"],
    "西南": ["成都", "重庆", "昆明", "贵阳", "绵阳"],
    "西北": ["西安", "兰州", "银川", "乌鲁木齐", "西宁"],
    "东北": ["沈阳", "大连", "哈尔滨", "长春", "鞍山"],
}

PRODUCT_NAMES = {
    "电子产品": ["智能手机Pro", "笔记本电脑Air", "无线蓝牙耳机", "平板电脑", "智能手表",
                "机械键盘", "4K显示器", "移动电源", "USB-C扩展坞", "无线路由器"],
    "办公用品": ["A4打印纸", "中性笔套装", "文件收纳架", "人体工学椅", "白板套装",
                "订书机", "计算器", "文件夹套装", "台灯", "笔记本"],
    "家居用品": ["保温杯", "收纳箱", "空气净化器", "扫地机器人", "加湿器",
                "LED台灯", "不锈钢锅具套装", "毛巾套装", "垃圾桶", "衣架套装"],
    "服装鞋帽": ["男士T恤", "女士连衣裙", "运动鞋", "羽绒服", "牛仔裤",
                "卫衣", "皮带", "棒球帽", "围巾", "休闲裤"],
    "食品饮料": ["坚果礼盒", "进口牛奶", "速溶咖啡", "方便面", "薯片",
                "矿泉水", "果汁", "巧克力", "饼干", "蜂蜜"],
    "美妆个护": ["面膜", "防晒霜", "洗面奶", "洗发水", "沐浴露",
                "口红", "粉底液", "眼霜", "香水", "电动牙刷"],
    "运动户外": ["瑜伽垫", "跑步机", "篮球", "登山包", "帐篷",
                "羽毛球拍", "跳绳", "哑铃套装", "运动水壶", "速干T恤"],
    "图书音像": ["管理学书籍", "编程入门", "历史小说", "经济学原理", "英语词典",
                "儿童绘本", "心理学著作", "科幻小说", "烹饪指南", "旅行随笔"],
    "母婴用品": ["婴儿奶粉", "纸尿裤", "婴儿推车", "积木玩具", "儿童水杯",
                "婴儿湿巾", "安全座椅", "早教机", "哺乳枕", "奶瓶"],
    "汽车配件": ["车载充电器", "行车记录仪", "车载香薰", "脚垫", "车载吸尘器",
                "雨刮器", "车蜡", "车载冰箱", "胎压监测", "遮阳挡"],
}

CUSTOMER_SEGMENTS = ["个人", "企业", "VIP"]
DEPARTMENTS = ["销售部", "技术部", "市场部", "运营部", "客服部"]
POSITIONS = ["销售经理", "销售代表", "技术主管", "市场专员", "运营经理", "客服主管"]
FIRST_NAMES = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴",
               "徐", "孙", "马", "朱", "胡", "郭", "林", "何", "高", "罗"]
LAST_CHARS = ["伟", "芳", "娜", "敏", "静", "强", "磊", "洋", "勇", "军",
              "杰", "丽", "明", "华", "慧", "建", "平", "刚", "秀英", "红"]
EMAIL_DOMAINS = ["qq.com", "163.com", "gmail.com", "outlook.com", "company.cn"]


def _random_name():
    return random.choice(FIRST_NAMES) + random.choice(LAST_CHARS) + random.choice(LAST_CHARS)


def _random_phone():
    prefixes = ["138", "139", "150", "151", "186", "187", "135", "136", "158", "159"]
    return random.choice(prefixes) + "".join([str(random.randint(0, 9)) for _ in range(8)])


def init_demo_data():
    tables = execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
    )
    if tables:
        return False

    _create_tables()
    _seed_categories()
    _seed_products()
    _seed_customers()
    _seed_employees()
    _seed_orders()
    return True


def _create_tables():
    stmts = [
        """CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            price REAL NOT NULL,
            cost REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            status TEXT DEFAULT '在售',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )""",
        """CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            region TEXT,
            city TEXT,
            segment TEXT DEFAULT '个人',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_spent REAL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT,
            position TEXT,
            region TEXT,
            hire_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            employee_id INTEGER,
            order_date TIMESTAMP NOT NULL,
            status TEXT DEFAULT '已完成',
            total_amount REAL DEFAULT 0,
            region TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )""",
        """CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount REAL DEFAULT 0,
            subtotal REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )""",
    ]
    for stmt in stmts:
        execute_update(stmt)


def _seed_categories():
    for name, desc in CATEGORIES:
        execute_update(
            "INSERT INTO categories (name, description) VALUES (:name, :desc)",
            {"name": name, "desc": desc},
        )


def _seed_products():
    for cat_id, (cat_name, _) in enumerate(CATEGORIES, 1):
        names = PRODUCT_NAMES[cat_name]
        for i, pname in enumerate(names):
            base_price = random.uniform(20, 5000)
            cost_ratio = random.uniform(0.3, 0.7)
            stock = random.randint(0, 2000)
            status = random.choice(["在售", "在售", "在售", "在售", "缺货"])
            execute_update(
                """INSERT INTO products (name, category_id, price, cost, stock, status)
                VALUES (:name, :cat_id, :price, :cost, :stock, :status)""",
                {
                    "name": pname,
                    "cat_id": cat_id,
                    "price": round(base_price, 2),
                    "cost": round(base_price * cost_ratio, 2),
                    "stock": stock,
                    "status": status,
                },
            )


def _seed_customers():
    for _ in range(500):
        region = random.choice(REGIONS)
        city = random.choice(CITIES[region])
        name = _random_name()
        email = f"{name}@{random.choice(EMAIL_DOMAINS)}"
        phone = _random_phone()
        segment = random.choices(CUSTOMER_SEGMENTS, weights=[60, 25, 15])[0]
        days_ago = random.randint(1, 730)
        reg_date = datetime.now() - timedelta(days=days_ago)
        execute_update(
            """INSERT INTO customers (name, email, phone, region, city, segment, registered_at)
            VALUES (:name, :email, :phone, :region, :city, :segment, :reg_date)""",
            {
                "name": name,
                "email": email,
                "phone": phone,
                "region": region,
                "city": city,
                "segment": segment,
                "reg_date": reg_date.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )


def _seed_employees():
    for i in range(20):
        region = random.choice(REGIONS)
        dept = random.choice(DEPARTMENTS)
        pos = random.choice(POSITIONS)
        days_ago = random.randint(180, 1825)
        hire = datetime.now() - timedelta(days=days_ago)
        execute_update(
            """INSERT INTO employees (name, department, position, region, hire_date)
            VALUES (:name, :dept, :pos, :region, :hire_date)""",
            {
                "name": _random_name(),
                "dept": dept,
                "pos": pos,
                "region": region,
                "hire_date": hire.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )


def _seed_orders():
    base_date = datetime.now() - timedelta(days=365)
    print("正在生成6000条订单数据（可能需要1-2分钟）...")

    for order_i in range(6000):
        if order_i % 1000 == 0 and order_i > 0:
            print(f"  已生成 {order_i}/6000 条订单...")

        customer_id = random.randint(1, 500)
        employee_id = random.randint(1, 20)
        day_offset = random.randint(0, 364)
        hour = random.choices(range(24), weights=[1]*6 + [3]*4 + [8]*8 + [5]*4 + [2]*2)[0]
        minute = random.randint(0, 59)
        order_date = base_date + timedelta(days=day_offset, hours=hour, minutes=minute)

        region = random.choice(REGIONS)
        status = random.choices(
            ["已完成", "已完成", "已完成", "已付款", "已发货", "已取消"],
            weights=[50, 20, 10, 5, 10, 5],
        )[0]

        num_items = random.randint(1, 5)
        product_ids = random.sample(range(1, 101), num_items)
        total = 0.0

        execute_update(
            """INSERT INTO orders (customer_id, employee_id, order_date, status, total_amount, region)
            VALUES (:cid, :eid, :odate, :status, 0, :region)""",
            {
                "cid": customer_id,
                "eid": employee_id,
                "odate": order_date.strftime("%Y-%m-%d %H:%M:%S"),
                "status": status,
                "region": region,
            },
        )
        order_row = execute_query("SELECT last_insert_rowid() as id")
        order_id = order_row[0]["id"]

        for pid in product_ids:
            prod = execute_query("SELECT price FROM products WHERE id = :id", {"id": pid})
            if not prod:
                continue
            unit_price = prod[0]["price"]
            qty = random.randint(1, 10)
            discount = random.choices([0, 0, 0, 0.05, 0.1, 0.15, 0.2], weights=[50, 20, 10, 8, 6, 4, 2])[0]
            subtotal = round(unit_price * qty * (1 - discount), 2)
            total += subtotal

            execute_update(
                """INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount, subtotal)
                VALUES (:oid, :pid, :qty, :uprice, :disc, :sub)""",
                {
                    "oid": order_id,
                    "pid": pid,
                    "qty": qty,
                    "uprice": unit_price,
                    "disc": discount,
                    "sub": subtotal,
                },
            )

        execute_update(
            "UPDATE orders SET total_amount = :total WHERE id = :id",
            {"total": round(total, 2), "id": order_id},
        )

    execute_update("""
        UPDATE customers SET total_spent = (
            SELECT COALESCE(SUM(total_amount), 0) FROM orders
            WHERE orders.customer_id = customers.id AND orders.status != '已取消'
        )
    """)
    print("订单数据生成完成！")
