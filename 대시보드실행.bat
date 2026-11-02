@echo off
title 견적·수주 통합 대시보드 실행
cd /d "%~dp0"
python -m streamlit run app.py
pause