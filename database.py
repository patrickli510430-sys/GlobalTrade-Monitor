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

from sqlmodel import SQLModel, create_engine, Session

sqlite_file_name = "trade_monitor.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session