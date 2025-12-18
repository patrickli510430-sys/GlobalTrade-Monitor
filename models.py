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

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

# 1. 用户表 (修复报错的关键)
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    password_hash: str

# 2. 商品表
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(unique=True, index=True)
    name: str
    currency: str = Field(default="USD") 
    cost_price: float 
    quantity: int
    safe_stock: int = 10 

# 3. 汇率表
class ExchangeRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    currency: str 
    rate_to_cny: float
    last_updated: datetime = Field(default_factory=datetime.now)

# 4. 日志表 (预留)
class StockLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int
    change_amount: int
    change_type: str 
    timestamp: datetime = Field(default_factory=datetime.now)