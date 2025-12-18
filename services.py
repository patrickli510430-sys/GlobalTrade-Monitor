# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   Project:   GlobalTrade Monitor
   File:      main.py
   Author:    [Wenxuan Li]
   Date:      2025-12-18
   Description:
      Main entry point for the FastAPI application.
      Handles routing, dependency injection, and app lifecycle.
-------------------------------------------------
   Copyright (c) 2025 [Wenxuan Li]. All rights reserved.
-------------------------------------------------
"""

import httpx
from datetime import datetime, timedelta
from sqlmodel import Session, select
from models import ExchangeRate

# 预设兜底汇率 (如果断网或 API Key 失效，用这些数据)
FALLBACK_RATES = {
    "USD": 7.25,
    "EUR": 7.85,
    "JPY": 0.048, # 100日元 ≈ 4.8元
    "GBP": 9.12
}

# 请替换为你的真实 API Key
API_KEY = "350b55728bbac44eef46757b" 
BASE_URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/"

async def get_exchange_rate(currency: str, session: Session) -> float:
    """
    获取汇率：优先查库，如果过期（>1小时）则调用API更新
    """
    if currency == "CNY":
        return 1.0

    # 1. 查询数据库
    statement = select(ExchangeRate).where(ExchangeRate.currency == currency)
    results = session.exec(statement)
    rate_entry = results.first()

    now = datetime.now()
    
    # 2. 判断是否需要更新 (不存在 或 超过1小时)
    if not rate_entry or (now - rate_entry.last_updated) > timedelta(hours=1):
        print(f"🔄 [系统日志] 正在尝试更新 {currency} 汇率...")
        
        try:
            # 设置 3秒超时，防止演示时卡死
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{BASE_URL}{currency}")
                
                # 检查 HTTP 状态码
                if response.status_code != 200:
                    raise Exception(f"API 响应错误: {response.status_code}")

                data = response.json()
                
                if data["result"] == "success":
                    new_rate = data["conversion_rates"]["CNY"]
                    print(f"✅ [API成功] {currency} -> CNY: {new_rate}")
                    
                    if rate_entry:
                        rate_entry.rate_to_cny = new_rate
                        rate_entry.last_updated = now
                    else:
                        rate_entry = ExchangeRate(currency=currency, rate_to_cny=new_rate)
                        session.add(rate_entry)
                    
                    session.commit()
                    session.refresh(rate_entry)
                    return new_rate
                else:
                    print(f"❌ [API失败] 错误类型: {data.get('error-type', '未知')}")
                    
        except Exception as e:
            print(f"⚠️ [网络/API异常] 获取 {currency} 失败，启用兜底数据。错误信息: {e}")
            # 如果数据库里有旧的，就先用旧的
            if rate_entry: 
                return rate_entry.rate_to_cny
            # 如果数据库也没有，就用写死的兜底数据
            return FALLBACK_RATES.get(currency, 1.0)
            
    return rate_entry.rate_to_cny