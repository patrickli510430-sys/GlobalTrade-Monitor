# ==============================================================================
# 1. 导入模块 (Imports)
# ==============================================================================
# 标准库
import asyncio
import csv
import io
import random
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

# 第三方库
from fastapi import FastAPI, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

# 本地模块
from database import create_db_and_tables, engine, get_session
from models import Product, StockLog, User, ExchangeRate
from services import get_exchange_rate


# ==============================================================================
# 2. 配置与常量 (Configuration & Constants)
# ==============================================================================
TRANSLATIONS = {
    "zh": {
        # --- 侧边栏 ---
        "nav_dashboard": "运营驾驶舱",
        "nav_inventory": "库存管理",
        "nav_settings": "系统设置",
        "nav_status_online": "系统在线",
        "switch_lang": "Switch to English",

        # --- Dashboard ---
        "portfolio_value": "全球库存总值",
        "analysis_ready": "分析就绪",
        "live_rates": "实时汇率",
        "stock_health": "库存健康度",
        "margin_analysis": "利润敏感度",
        "fund_dist": "资金分布",
        "ask_ai": "智能咨询",
        "ai_thinking": "正在分析市场数据...",
        "gen_data": "生成数据",
        "modal_title": "资产深度分析",
        "modal_trend": "近30天资产趋势",
        "modal_cat": "品类占比",
        "close": "关闭",
        
        # 图表相关
        "chart_stock_title": "库存深度排行",
        "chart_stock_sub": "当前实时库存量",
        "chart_trend_title": "库存动向",
        "chart_trend_sub": "当前库存",
        "chart_safe_stock": "安全库存",
        "chart_profit_rate": "预估利润率",
        "chart_rate_index": "汇率波动指数",
        "chart_profit_y": "利润率 (%)",
        "chart_rate_y": "汇率指数",
        "pie_usd": "美元资产",
        "pie_eur": "欧元资产",
        "pie_jpy": "日元资产",
        "pie_gbp": "英镑资产",
        "pie_other": "其他",
        "modal_elec": "电子产品",
        "modal_fashion": "时尚单品",
        "modal_home": "家居用品",
        "modal_beauty": "美妆护肤",

        # Dashboard 下拉框
        "select_top15": "Top 15 总览",
        "optgroup_trends": "单品趋势",

        # --- 库存页面 (Inventory) ---
        "inv_title": "全球库存清单",
        "inv_subtitle": "支持 USD, EUR, JPY, GBP 多币种混合管理",
        "btn_mock": "生成模拟数据",
        "btn_import": "导入 CSV",
        "btn_add_item": "新增商品",
        "th_sku": "SKU / 名称",
        "th_cost": "原币种成本",
        "th_status": "库存状态",
        "th_action": "操作",
        "status_ok": "充足",
        "status_low": "缺货",

        # --- 设置页面 (Settings) ---
        "set_title": "系统设置",
        "set_subtitle": "管理您的账户安全与数据资产",
        "set_tab_general": "通用设置",
        "set_tab_users": "账号管理",
        "set_tab_backup": "数据备份",
        "set_pref_title": "系统偏好",
        "lbl_base_curr": "系统本位币",
        "lbl_safe_stock": "库存预警阈值",
        "cny_label": "CNY (人民币)",
        "usd_label": "USD (美元)",
        "lbl_auto_update": "自动汇率更新",
        "lbl_auto_update_sub": "每小时同步 ExchangeRate-API",
        "btn_save": "保存更改",
        "set_team_title": "团队成员",
        "btn_add_member": "添加成员",
        "set_backup_title": "数据安全中心",
        "card_backup_title": "导出数据备份",
        "card_backup_desc": "下载当前的数据库文件 (.db)。",
        "btn_download": "立即下载",
        "card_restore_title": "恢复数据",
        "card_restore_desc": "上传之前备份的 .db 文件。",
        "btn_restore": "开始恢复",
        "danger_zone": "危险区域",
        "btn_reset": "重置数据",
        "tab_profit": "利润", 
        "tab_fund": "资金"
    },
    "en": {
        # --- Sidebar ---
        "nav_dashboard": "Cockpit",
        "nav_inventory": "Inventory",
        "nav_settings": "Settings",
        "nav_status_online": "System Online",
        "switch_lang": "切换中文",

        # --- Dashboard ---
        "portfolio_value": "Portfolio Value",
        "analysis_ready": "Analysis Ready",
        "live_rates": "Live Rates",
        "stock_health": "Stock Health",
        "margin_analysis": "Margin Sensitivity",
        "fund_dist": "Fund Distribution",
        "ask_ai": "Ask AI",
        "ai_thinking": "Analyzing market data...",
        "gen_data": "Generate Data",
        "modal_title": "Portfolio Deep Dive",
        "modal_trend": "30-Day Asset Trend",
        "modal_cat": "Category Breakdown",
        "close": "Close",

        # Charts
        "chart_stock_title": "Inventory Depth Rank",
        "chart_stock_sub": "Real-time Stock Level",
        "chart_trend_title": "Inventory Trend",
        "chart_trend_sub": "Current Stock",
        "chart_safe_stock": "Safe Stock",
        "chart_profit_rate": "Est. Profit Margin",
        "chart_rate_index": "Exchange Rate Index",
        "chart_profit_y": "Margin (%)",
        "chart_rate_y": "Rate Index",
        "pie_usd": "USD Assets",
        "pie_eur": "EUR Assets",
        "pie_jpy": "JPY Assets",
        "pie_gbp": "GBP Assets",
        "pie_other": "Other",
        "modal_elec": "Electronics",
        "modal_fashion": "Fashion",
        "modal_home": "Home",
        "modal_beauty": "Beauty",

        # Dashboard Dropdown
        "select_top15": "Top 15 Overview",
        "optgroup_trends": "Item Trends",

        # --- Inventory Page ---
        "inv_title": "Global Inventory",
        "inv_subtitle": "Supports USD, EUR, JPY, GBP mixed management",
        "btn_mock": "Generate Mock Data",
        "btn_import": "Import CSV",
        "btn_add_item": "Add Item",
        "th_sku": "SKU / Name",
        "th_cost": "Cost (Original Currency)",
        "th_status": "Status",
        "th_action": "Action",
        "status_ok": "In Stock",
        "status_low": "Low Stock",

        # --- Settings Page ---
        "set_title": "System Settings",
        "set_subtitle": "Manage account security and data assets",
        "set_tab_general": "General",
        "set_tab_users": "Team & Users",
        "set_tab_backup": "Backup & Restore",
        "set_pref_title": "Preferences",
        "lbl_base_curr": "Base Currency",
        "lbl_safe_stock": "Safe Stock Threshold",
        "cny_label": "CNY (Chinese Yuan)",
        "usd_label": "USD (US Dollar)",
        "lbl_auto_update": "Auto Rate Update",
        "lbl_auto_update_sub": "Syncs hourly with ExchangeRate-API",
        "btn_save": "Save Changes",
        "set_team_title": "Team Members",
        "btn_add_member": "Add Member",
        "set_backup_title": "Data Security Center",
        "card_backup_title": "Export Backup",
        "card_backup_desc": "Download current database file (.db).",
        "btn_download": "Download Now",
        "card_restore_title": "Restore Data",
        "card_restore_desc": "Upload a previously backed up .db file.",
        "btn_restore": "Start Restore",
        "danger_zone": "Danger Zone",
        "btn_reset": "Reset Data",
        "tab_profit": "Profit", 
        "tab_fund": "Fund" 
    }
}


# ==============================================================================
# 3. 生命周期与应用初始化 (Lifespan & App Init)
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库表
    create_db_and_tables()
    # 预置数据：覆盖 美、欧、日、英
    with Session(engine) as session:
        if not session.exec(select(Product)).first():
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

# 挂载静态资源与模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ==============================================================================
# 4. 页面路由 (Page Routes)
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: Session = Depends(get_session)):
    """主仪表盘页面"""
    lang = request.cookies.get("app_lang", "zh")
    t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
    
    products = session.exec(select(Product)).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "products": products,
        "t": t,
        "current_lang": lang
    })

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, session: Session = Depends(get_session)):
    """库存管理页面"""
    lang = request.cookies.get("app_lang", "zh")
    t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
    
    products = session.exec(select(Product)).all()
    
    return templates.TemplateResponse("inventory.html", {
        "request": request, 
        "products": products,
        "t": t,
        "current_lang": lang
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, session: Session = Depends(get_session)):
    """系统设置页面"""
    lang = request.cookies.get("app_lang", "zh")
    t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
    
    users = session.exec(select(User)).all()
    # 默认创建一个管理员，防止列表为空
    if not users:
        admin = User(username="admin", password_hash="123456")
        session.add(admin)
        session.commit()
        session.refresh(admin)
        users = [admin]

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "users": users,
        "t": t,
        "current_lang": lang
    })


# ==============================================================================
# 5. Dashboard 组件 API (Dashboard Widgets & Stats)
# ==============================================================================
@app.get("/api/dashboard-stats")
async def get_dashboard_stats(request: Request, session: Session = Depends(get_session)):
    """获取 KPI 卡片数据 (HTMX 轮询)"""
    lang = request.cookies.get("app_lang", "zh")
    t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
    
    products = session.exec(select(Product)).all()
    currencies = ["USD", "EUR", "JPY", "GBP"]
    
    # 获取汇率
    rates = {}
    for c in currencies:
        rates[c] = await get_exchange_rate(c, session)
        
    # 计算总价值
    total_value = 0.0
    for p in products:
        r = rates.get(p.currency, 1.0)
        total_value += p.quantity * p.cost_price * r

    return templates.TemplateResponse("partials/stats_cards.html", {
        "request": request,
        "total_value": total_value,
        "rates": rates,
        "t": t
    })

@app.get("/api/ticker")
async def get_ticker_html(session: Session = Depends(get_session)):
    """顶部滚动条 HTML"""
    currencies = ["USD", "EUR", "JPY", "GBP"]
    rates = {}
    
    for c in currencies:
        rates[c] = await get_exchange_rate(c, session)
        
    items_html = ""
    for _ in range(2): # 重复两次以实现无缝滚动
        for curr, rate in rates.items():
            change = random.uniform(-0.5, 0.5)
            color_class = "text-emerald-400" if change >= 0 else "text-rose-400"
            sign = "+" if change >= 0 else ""
            
            items_html += f"""
            <div class="flex items-center gap-2">
                <span class="text-slate-500 font-bold uppercase">{curr}/CNY</span>
                <span class="font-black text-indigo-400">{rate:.4f}</span>
                <span class="text-[10px] {color_class}">{sign}{change:.2f}%</span>
            </div>
            """
            
    return HTMLResponse(f"""
        <div class="flex animate-marquee whitespace-nowrap gap-16 pl-32">
            {items_html}
        </div>
    """)


# ==============================================================================
# 6. 图表数据 API (Charts API)
# ==============================================================================
@app.get("/api/chart/product/{product_id}")
async def get_product_chart(request: Request, product_id: str, session: Session = Depends(get_session)):
    """主图表：库存深度 / 单品趋势"""
    lang = request.cookies.get("app_lang", "zh")
    t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])

    if product_id == "all":
        # --- Top 15 总览模式 ---
        title = t['chart_stock_title']
        subtext = t['chart_stock_sub']
        
        products = session.exec(select(Product)).all()
        products.sort(key=lambda x: x.quantity, reverse=True)
        top_products = products[:15]
        
        # 简单处理：如果是演示数据，可以尝试翻译商品名，实际项目中直接显示原名即可
        chart_names = [p.name for p in top_products]
        chart_values = [p.quantity for p in top_products]
        
        return templates.TemplateResponse("partials/chart_area.html", {
            "request": request,
            "chart_type": "bar",
            "title": title,
            "subtext": subtext,
            "names": chart_names,
            "values": chart_values,
            "color": "#3b82f6",
            "t": t
        })
    else:
        # --- 单品历史趋势模式 ---
        product = session.get(Product, int(product_id))
        if not product:
            return HTMLResponse("Product not found", status_code=404)
        
        title = f"【{product.name}】{t['chart_trend_title']}"
        subtext = f"{t['chart_trend_sub']}: {product.quantity} | {t['chart_safe_stock']}: {product.safe_stock}"
        
        dates = [(datetime.now() - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
        current_qty = product.quantity
        history_values = []

        # 剧本逻辑：奇数ID为热销，偶数ID为补货
        if product.id % 2 != 0: 
            for i in range(7):
                simulated_val = current_qty + (i * random.randint(5, 10))
                history_values.insert(0, simulated_val)
            color = "#f43f5e" # 红
        else:
            for i in range(7):
                if i < 2:
                    simulated_val = current_qty + random.randint(-2, 2)
                else:
                    simulated_val = max(0, current_qty - 100 + random.randint(-5, 5))
                history_values.insert(0, simulated_val)
            color = "#10b981" # 绿

        return templates.TemplateResponse("partials/chart_area.html", {
            "request": request,
            "chart_type": "line",
            "title": title,
            "subtext": subtext,
            "names": dates,
            "values": history_values,
            "color": color,
            "t": t
        })

@app.get("/api/chart/pie")
async def get_pie_chart(request: Request, session: Session = Depends(get_session)):
    """右侧：资金分布饼图"""
    lang = request.cookies.get("app_lang", "zh")
    t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])

    products = session.exec(select(Product)).all()
    asset_map = {"USD": 0.0, "EUR": 0.0, "JPY": 0.0, "GBP": 0.0, "Other": 0.0}
    
    # 缓存汇率
    rates = {}
    for c in ["USD", "EUR", "JPY", "GBP"]:
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
        "asset_map": asset_map,
        "t": t
    })

@app.get("/api/chart/profit")
async def get_profit_chart(request: Request):
    """右侧：汇率波动 vs 利润率"""
    lang = request.cookies.get("app_lang", "zh")
    t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
    
    dates = [(datetime.now() - timedelta(days=i)).strftime("%m-%d") for i in range(6, -1, -1)]
    base_margin = 25.0
    
    rate_trend = []
    profit_trend = []
    current_rate_idx = 100
    
    for _ in range(7):
        change = random.uniform(-1.5, 1.5)
        current_rate_idx += change
        rate_trend.append(round(current_rate_idx, 1))
        
        margin_impact = change * 0.8
        new_margin = base_margin - margin_impact
        profit_trend.append(round(new_margin, 2))

    return templates.TemplateResponse("partials/chart_profit.html", {
        "request": request,
        "dates": dates,
        "profit_trend": profit_trend,
        "rate_trend": rate_trend,
        "t": t
    })


# ==============================================================================
# 7. 功能与业务逻辑 API (Functional APIs)
# ==============================================================================
@app.get("/api/set-lang/{lang_code}")
async def set_language(lang_code: str):
    """切换语言并设置 Cookie"""
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="app_lang", value=lang_code)
    return response

@app.post("/api/ai/ask")
async def ask_ai_insight(request: Request):
    """模拟 AI 分析"""
    await asyncio.sleep(1.5)
    lang = request.cookies.get("app_lang", "zh")
    
    if lang == "zh":
        insight = """
        <strong>Flux AI 市场洞察：</strong><br><br>
        1. <strong>汇率风险警报：</strong> 美元 (USD) 近期波动较大，建议对高价值电子产品进行锁汇处理，预计可规避 3.5% 的汇率损失。<br>
        2. <strong>库存优化：</strong> 检测到 "Sony A7M4" 库存周转率下降，建议在汇率高点进行促销。<br>
        3. <strong>资金建议：</strong> 目前日元资产占比过低，建议适当增加 JPY 结算商品的储备以平衡风险组合。
        """
    else:
        insight = """
        <strong>Flux AI Market Insight:</strong><br><br>
        1. <strong>FX Risk Alert:</strong> High volatility detected in USD. Hedging high-value electronics is recommended to avoid a projected 3.5% loss.<br>
        2. <strong>Inventory Optimization:</strong> "Sony A7M4" turnover is slowing down. Consider a promotion while exchange rates are favorable.<br>
        3. <strong>Capital Strategy:</strong> JPY exposure is too low. Recommend increasing JPY-denominated inventory to balance the risk portfolio.
        """
    
    return HTMLResponse(f"""
        <div class="bg-indigo-50 border border-indigo-100 p-6 rounded-2xl animate-[fadeIn_0.5s_ease-out]">
            <div class="flex items-center gap-3 mb-4">
                <div class="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white">
                    <i class="fa-solid fa-robot"></i>
                </div>
                <span class="font-bold text-indigo-900">AI Analysis Report</span>
            </div>
            <div class="text-slate-700 leading-relaxed text-sm">
                {insight}
            </div>
        </div>
    """)

@app.post("/api/generate-data")
async def generate_mock_data(session: Session = Depends(get_session)):
    """智能模拟数据生成器"""
    # 模拟数据剧本
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
        # Upsert 逻辑
        existing_product = session.exec(select(Product).where(Product.name == name)).first()
        
        if existing_product:
            # 更新库存与价格
            stock_change = random.randint(-5, 10)
            existing_product.quantity = max(0, existing_product.quantity + stock_change)
            price_fluctuation = random.uniform(0.98, 1.02)
            existing_product.cost_price = round(existing_product.cost_price * price_fluctuation, 2)
            session.add(existing_product)
            updated_count += 1
        else:
            # 创建新商品
            sku_rand = random.randint(1000, 9999)
            new_p = Product(
                sku=f"{currency}-{sku_rand}",
                name=name,
                currency=currency,
                cost_price=round(random.uniform(min_p, max_p), 2),
                quantity=random.randint(5, 50),
                safe_stock=safe_s
            )
            session.add(new_p)
            added_count += 1
    
    session.commit()
    
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

@app.post("/api/import-csv")
async def import_csv(file: UploadFile = File(...), session: Session = Depends(get_session)):
    """CSV 批量导入"""
    content = await file.read()
    decoded = content.decode('utf-8').splitlines()
    reader = csv.reader(decoded)
    next(reader, None) # 跳过表头
    
    count = 0
    for row in reader:
        try:
            if len(row) < 5: continue
            p = Product(
                sku=row[0], name=row[1], currency=row[2],
                cost_price=float(row[3]), quantity=int(row[4]), safe_stock=10
            )
            session.add(p)
            count += 1
        except Exception:
            continue
    session.commit()
    
    return HTMLResponse(
        content=f"""
        <div class="fixed bottom-4 right-4 bg-blue-600 text-white px-6 py-4 rounded-xl shadow-2xl animate-bounce">
            <i class="fa-solid fa-check-circle"></i> 成功导入 {count} 条数据！
        </div>
        """,
        headers={"HX-Refresh": "true"}
    )


# ==============================================================================
# 8. CRUD 操作 (Products & Users)
# ==============================================================================
@app.post("/products/add")
async def add_product(
    name: str = Form(...), sku: str = Form(...), currency: str = Form(...),
    cost_price: float = Form(...), quantity: int = Form(...),
    session: Session = Depends(get_session)
):
    """添加商品"""
    new_product = Product(name=name, sku=sku, currency=currency, cost_price=cost_price, quantity=quantity)
    session.add(new_product)
    session.commit()
    return HTMLResponse(headers={"HX-Refresh": "true"})

@app.delete("/products/{product_id}")
async def delete_product(product_id: int, session: Session = Depends(get_session)):
    """删除商品"""
    product = session.get(Product, product_id)
    if product:
        session.delete(product)
        session.commit()
    return HTMLResponse(content="")

@app.post("/settings/users/add")
async def add_user(username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    """添加用户"""
    new_user = User(username=username, password_hash=password)
    session.add(new_user)
    session.commit()
    return HTMLResponse(headers={"HX-Refresh": "true"})

@app.delete("/settings/users/{user_id}")
async def delete_user(user_id: int, session: Session = Depends(get_session)):
    """删除用户"""
    user = session.get(User, user_id)
    if user:
        session.delete(user)
        session.commit()
    return HTMLResponse("")


# ==============================================================================
# 9. 系统备份与恢复 (System Backup & Restore)
# ==============================================================================
@app.get("/api/system/backup")
async def backup_database():
    """下载数据库备份"""
    file_path = "trade_monitor.db"
    return FileResponse(
        path=file_path, 
        filename=f"backup_{datetime.now().strftime('%Y%m%d')}.db",
        media_type='application/octet-stream'
    )

@app.post("/api/system/restore")
async def restore_database(file: UploadFile = File(...)):
    """上传并还原数据库"""
    try:
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