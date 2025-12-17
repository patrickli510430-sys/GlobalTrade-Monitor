import random
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from database import create_db_and_tables, engine, get_session
from models import Product, StockLog, User
from services import get_exchange_rate
from datetime import datetime, timedelta
import csv
import io
from fastapi import UploadFile, File
import shutil # 用于文件复制
from fastapi.responses import FileResponse # 用于文件下载

# --- 1. 升级版生命周期：预置多国数据 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        if not session.exec(select(Product)).first():
            # 预置数据：覆盖 美、欧、日、英
            seed_data = [
                Product(sku="US-001", name="NVIDIA RTX 4090", currency="USD", cost_price=1599.0, quantity=5, safe_stock=10),
                Product(sku="EU-DE-01", name="德国精酿啤酒桶", currency="EUR", cost_price=85.5, quantity=200, safe_stock=50),
                Product(sku="JP-SONY-X", name="Sony A7M4 相机", currency="JPY", cost_price=240000, quantity=15, safe_stock=5),
                Product(sku="UK-TEA-01", name="皇室红茶礼盒", currency="GBP", cost_price=45.0, quantity=80, safe_stock=20),
            ]
            session.add_all(seed_data)
            session.commit()
    yield

app = FastAPI(lifespan=lifespan)
# 挂载 static 目录，解决 favicon 问题
# 如果你没有真正的 favicon.ico，创建一个空文件放在 static 文件夹里也可以
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ... (保持原有的页面路由 dashboard 和 inventory_page 不变) ...
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: Session = Depends(get_session)):
    """主 Dashboard 页面"""
    # 1. 从数据库获取所有商品，以便在前端下拉框显示
    products = session.exec(select(Product)).all()
    
    # 2. 将 products 传递给模板
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "products": products
    })

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, session: Session = Depends(get_session)):
    products = session.exec(select(Product)).all()
    return templates.TemplateResponse("inventory.html", {"request": request, "products": products})


# --- 1. 修复并精简 KPI 接口 (只返回顶部卡片) ---
@app.get("/api/dashboard-stats")
async def get_dashboard_stats(request: Request, session: Session = Depends(get_session)):
    """只负责计算顶部的 KPI 数字和汇率，不再返回图表数据"""
    products = session.exec(select(Product)).all()
    
    # 获取汇率
    currencies = ["USD", "EUR", "JPY", "GBP"]
    rates = {}
    for c in currencies:
        rates[c] = await get_exchange_rate(c, session)

    total_value_cny = 0.0
    
    for p in products:
        rate = rates.get(p.currency, 1.0)
        # 如果汇率获取失败（兜底逻辑），确保程序不崩
        if not rate: rate = 1.0 
        total_value_cny += p.quantity * p.cost_price * rate

    # 🔴 注意：这里不再计算 chart_names/values，减少后端压力
    return templates.TemplateResponse("partials/stats_cards.html", {
        "request": request,
        "total_value": total_value_cny,
        "rates": rates
    })

# --- 3. 新增：一键生成模拟数据 (演示神器) ---
# main.py

@app.post("/api/generate-data")
async def generate_mock_data(session: Session = Depends(get_session)):
    """
    智能模拟数据生成器
    逻辑：如果商品已存在，则模拟库存/价格波动；如果不存在，则创建。
    """
    import random
    
    # 1. 定义一个高质量的“固定剧本”数据池
    # 格式：(币种, 商品名称, 最低价, 最高价, 安全库存)
    mock_scenarios = [
        ("USD", "Apple iPhone 15 Pro", 999, 1099, 20),
        ("USD", "NVIDIA RTX 4090", 1599, 1799, 5),
        ("USD", "Tesla Model 3 模型", 35, 50, 50),
        ("EUR", "Dior 999 烈焰蓝金", 35, 45, 100),
        ("EUR", "Le Creuset 铸铁锅", 200, 300, 10),
        ("EUR", "Chanel N°5 香水", 120, 150, 30),
        ("JPY", "Sony PlayStation 5", 45000, 55000, 15),
        ("JPY", "SK-II 神仙水 230ml", 15000, 22000, 40),
        ("JPY", "Nintendo Switch OLED", 32000, 38000, 25),
        ("GBP", "Jellycat 邦尼兔", 20, 35, 50),
        ("GBP", "Dyson V15 Detect", 500, 600, 10),
        ("GBP", "Whittard 经典红茶", 15, 25, 100),
    ]

    added_count = 0
    updated_count = 0
    
    for currency, name, min_p, max_p, safe_s in mock_scenarios:
        # 2. 核心逻辑：先查库，看这个商品名字是否已存在
        statement = select(Product).where(Product.name == name)
        existing_product = session.exec(statement).first()
        
        if existing_product:
            # --- 分支 A: 商品已存在 -> 模拟市场波动 ---
            # 模拟库存变化：随机卖出或补货 (-5 到 +10)
            stock_change = random.randint(-5, 10)
            existing_product.quantity = max(0, existing_product.quantity + stock_change)
            
            # 模拟进货价波动：在原价基础上浮动 ±2%
            price_fluctuation = random.uniform(0.98, 1.02)
            existing_product.cost_price = round(existing_product.cost_price * price_fluctuation, 2)
            
            session.add(existing_product)
            updated_count += 1
            
        else:
            # --- 分支 B: 商品不存在 -> 创建新商品 ---
            # 生成一个随机但看起来很真的 SKU
            sku_rand = random.randint(1000, 9999)
            
            new_p = Product(
                sku=f"{currency}-{sku_rand}", # 例如 USD-4092
                name=name,
                currency=currency,
                cost_price=round(random.uniform(min_p, max_p), 2),
                quantity=random.randint(5, 50), # 初始随机库存
                safe_stock=safe_s
            )
            session.add(new_p)
            added_count += 1
    
    session.commit()
    
    # 3. 返回动态提示信息
    msg_color = "bg-blue-600" if added_count > 0 else "bg-purple-600"
    msg_text = f"新增 {added_count} 款新品" if added_count > 0 else f"已更新 {updated_count} 款商品的库存与价格"
    
    return HTMLResponse(
        content=f"""
        <div class="fixed bottom-4 right-4 {msg_color} text-white px-6 py-4 rounded-xl shadow-2xl animate-bounce flex items-center gap-3 z-50">
            <i class="fa-solid fa-check-circle text-xl"></i>
            <div>
                <p class="font-bold text-lg">数据模拟完成</p>
                <p class="text-sm opacity-90">{msg_text}</p>
            </div>
        </div>
        """, 
        headers={"HX-Refresh": "true"}
    )

# --- 保持原有的 CRUD 接口 ---
@app.post("/products/add")
async def add_product(
    name: str = Form(...), 
    sku: str = Form(...), 
    currency: str = Form(...),
    cost_price: float = Form(...),
    quantity: int = Form(...),
    session: Session = Depends(get_session)
):
    # ... (保持之前的代码不变)
    new_product = Product(name=name, sku=sku, currency=currency, cost_price=cost_price, quantity=quantity)
    session.add(new_product)
    session.commit()
    session.refresh(new_product)
    # 为了演示方便，这里我们简单地触发页面刷新
    return HTMLResponse(headers={"HX-Refresh": "true"})

@app.delete("/products/{product_id}")
async def delete_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if product:
        session.delete(product)
        session.commit()
    return HTMLResponse(content="")

# --- 2. 修复：折线图接口 (修复 datetime 报错) ---
# main.py

@app.get("/api/chart/product/{product_id}")
async def get_product_chart(request: Request, product_id: str, session: Session = Depends(get_session)):
    
    if product_id == "all":
        # ... (保持原有的 Top 15 逻辑不变) ...
        products = session.exec(select(Product)).all()
        products.sort(key=lambda x: x.quantity, reverse=True)
        top_products = products[:15]
        chart_names = [p.name for p in top_products]
        chart_values = [p.quantity for p in top_products]
        
        return templates.TemplateResponse("partials/chart_area.html", {
            "request": request,
            "chart_type": "bar",
            "title": "Top 15 库存深度排行",
            "subtext": "当前实时库存量",
            "names": chart_names,
            "values": chart_values,
            "color": "#3b82f6"
        })
    else:
        # 单品模式：根据 product_id 的奇偶性，给不同的“剧本”
        product = session.get(Product, int(product_id))
        if not product:
            return HTMLResponse("商品不存在", status_code=404)
            
        dates = [(datetime.now() - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
        current_qty = product.quantity
        history_values = []

        # 🔴 剧本 A：热销爆款 (库存持续快速下降)
        if product.id % 2 != 0: 
            # 倒推历史：当前是 5，昨天可能是 15，前天 25...
            for i in range(7):
                # 每天卖出 5-10 个
                simulated_val = current_qty + (i * random.randint(5, 10))
                history_values.insert(0, simulated_val)
            
            title_text = f"【{product.name}】销售火爆 (需补货)"
            color = "#f43f5e" # 红色预警

        # 🔴 剧本 B：刚刚补货 (之前很低，突然拉高)
        else:
            # 模拟：前几天很低，昨天突然补货进来了
            for i in range(7):
                if i < 2: # 最近两天是当前的高库存
                    simulated_val = current_qty + random.randint(-2, 2)
                else: # 两天前库存很低
                    simulated_val = max(0, current_qty - 100 + random.randint(-5, 5))
                history_values.insert(0, simulated_val)
            
            title_text = f"【{product.name}】近日已补货完成"
            color = "#10b981" # 绿色健康

        return templates.TemplateResponse("partials/chart_area.html", {
            "request": request,
            "chart_type": "line",
            "title": title_text,
            "subtext": f"当前库存: {product.quantity} | 安全库存: {product.safe_stock}",
            "names": dates,
            "values": history_values,
            "color": color
        })

# --- 新增功能 2: 批量导入 CSV ---
@app.post("/api/import-csv")
async def import_csv(file: UploadFile = File(...), session: Session = Depends(get_session)):
    """解析上传的 CSV 文件并批量插入"""
    content = await file.read()
    # 解码 CSV
    decoded = content.decode('utf-8').splitlines()
    reader = csv.reader(decoded)
    
    # 跳过表头 (假设第一行是 Header)
    header = next(reader, None)
    
    count = 0
    for row in reader:
        try:
            # 假设 CSV 格式: SKU, Name, Currency, Cost, Quantity
            # 例如: A001, TestItem, USD, 10.5, 100
            if len(row) < 5: continue
            
            p = Product(
                sku=row[0],
                name=row[1],
                currency=row[2],
                cost_price=float(row[3]),
                quantity=int(row[4]),
                safe_stock=10 # 默认值
            )
            session.add(p)
            count += 1
        except Exception as e:
            print(f"Skipping row {row}: {e}")
            continue
            
    session.commit()
    
    return HTMLResponse(
        content=f"""
        <div class="fixed bottom-4 right-4 bg-blue-600 text-white px-6 py-4 rounded-xl shadow-2xl animate-bounce">
            <i class="fa-solid fa-check-circle"></i> 成功导入 {count} 条数据！
        </div>
        """,
        headers={"HX-Refresh": "true"} # 刷新页面显示新数据
    )

# --- 系统设置页面 (升级版) ---
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, session: Session = Depends(get_session)):
    """
    渲染设置页面，同时预加载用户列表
    """
    # 获取所有用户用于展示
    users = session.exec(select(User)).all()
    # 如果没有用户，创建一个默认管理员 (防止空列表难看)
    if not users:
        admin = User(username="admin", password_hash="123456") # 演示用明文/简单Hash
        session.add(admin)
        session.commit()
        session.refresh(admin)
        users = [admin]

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "users": users
    })

# --- 用户管理接口 ---
@app.post("/settings/users/add")
async def add_user(
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    """添加新用户"""
    # 实际项目中这里应该 Hash 密码
    new_user = User(username=username, password_hash=password)
    session.add(new_user)
    session.commit()
    # 添加成功后刷新页面 (简单粗暴，或者返回 HTML 片段)
    return HTMLResponse(headers={"HX-Refresh": "true"})

@app.delete("/settings/users/{user_id}")
async def delete_user(user_id: int, session: Session = Depends(get_session)):
    """删除用户"""
    user = session.get(User, user_id)
    if user:
        session.delete(user)
        session.commit()
    return HTMLResponse("")

# --- 数据备份与恢复接口 ---
@app.get("/api/system/backup")
async def backup_database():
    """下载 SQLite 数据库文件"""
    file_path = "trade_monitor.db"
    return FileResponse(
        path=file_path, 
        filename=f"backup_{datetime.now().strftime('%Y%m%d')}.db",
        media_type='application/octet-stream'
    )

@app.post("/api/system/restore")
async def restore_database(file: UploadFile = File(...)):
    """上传并覆盖数据库文件"""
    try:
        # 将上传的文件保存为 trade_monitor.db
        with open("trade_monitor.db", "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return HTMLResponse("""
            <div class="bg-green-100 border-l-4 border-green-500 text-green-700 p-4 mb-4" role="alert">
                <p class="font-bold">恢复成功</p>
                <p>数据库已还原，请刷新页面。</p>
            </div>
        """)
    except Exception as e:
        return HTMLResponse(f"""
            <div class="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4" role="alert">
                <p class="font-bold">恢复失败</p>
                <p>{str(e)}</p>
            </div>
        """)

# --- 3. 新增：独立的饼图接口 ---
@app.get("/api/chart/pie")
async def get_pie_chart(request: Request, session: Session = Depends(get_session)):
    """右侧：资金分布饼图"""
    products = session.exec(select(Product)).all()
    
    asset_map = {"USD": 0.0, "EUR": 0.0, "JPY": 0.0, "GBP": 0.0, "Other": 0.0}
    
    # 简单的汇率缓存
    rates = {}
    currencies = ["USD", "EUR", "JPY", "GBP"]
    for c in currencies:
        rates[c] = await get_exchange_rate(c, session)

    for p in products:
        rate = rates.get(p.currency, 1.0)
        val_cny = p.quantity * p.cost_price * rate
        
        if p.currency in asset_map:
            asset_map[p.currency] += val_cny
        else:
            asset_map["Other"] += val_cny

    return templates.TemplateResponse("partials/chart_pie.html", {
        "request": request,
        "asset_map": asset_map
    })

@app.get("/api/chart/profit")
async def get_profit_chart(request: Request, session: Session = Depends(get_session)):
    """
    生成【汇率波动 vs 利润率】趋势图
    模拟逻辑：假设商品售价固定(CNY)，当外币汇率上涨，进货成本(CNY)变高，利润率下降。
    """
    import random
    
    # 生成过去 7 天的日期
    dates = [(datetime.now() - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
    
    # 模拟基础数据
    base_margin = 25.0 # 基础毛利率 25%
    
    # 模拟汇率波动对利润的冲击 (反向关联)
    # 汇率线 (模拟归一化趋势)
    rate_trend = []
    # 利润线
    profit_trend = []
    
    current_rate_idx = 100
    
    for _ in range(7):
        # 模拟汇率每天波动 -1% 到 +1%
        change = random.uniform(-1.5, 1.5)
        current_rate_idx += change
        rate_trend.append(round(current_rate_idx, 1))
        
        # 利润率反向波动：汇率涨1%，利润跌0.8% (假设)
        margin_impact = change * 0.8
        new_margin = base_margin - margin_impact
        profit_trend.append(round(new_margin, 2))

    return templates.TemplateResponse("partials/chart_profit.html", {
        "request": request,
        "dates": dates,
        "profit_trend": profit_trend,
        "rate_trend": rate_trend
    })