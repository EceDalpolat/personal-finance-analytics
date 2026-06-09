"""ai-engine — bağımsız AI servisi (internal FastAPI app).

Sorumluluklar:
- api/'den gelen chat sorularını işler (routers/chat.py)
- dbt build sonrası insight üretimini tetikler (routers/insights.py)
- scheduled runner'ları barındırır (anomaly, recommendation)
"""
# TODO: FastAPI app, router'ları include et, lifespan'de DB pool + tracing kur.
