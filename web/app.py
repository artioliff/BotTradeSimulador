import os
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from backtest import (
    gerar_dados_sinteticos,
    gerar_tendencia_com_mudancas,
    executar_backtest,
    comparar_estrategias,
    print_relatorio,
)

BASE_DIR = Path(__file__).parent

estrategias_disponiveis = {
    "rsi": {"nome": "RSI", "modulo": "RSIStrategy", "arquivo": "estrategias.rsi"},
    "rsi_avancado": {"nome": "RSI Avançado", "modulo": "RSIAvancadoStrategy", "arquivo": "estrategias.rsi_avancado"},
    "macd": {"nome": "MACD", "modulo": "MACDStrategy", "arquivo": "estrategias.macd"},
    "bollinger": {"nome": "Bollinger Bands", "modulo": "BollingerBandsStrategy", "arquivo": "estrategias.bollinger"},
    "adx": {"nome": "ADX", "modulo": "ADXStrategy", "arquivo": "estrategias.adx"},
    "combinacao": {"nome": "Combinação", "modulo": "CombinacaoStrategy", "arquivo": "estrategias.combinacao"},
    "grid": {"nome": "Grid Spot", "modulo": "GridSpotStrategy", "arquivo": "estrategias.grid_spot"},
    "media_movel": {"nome": "Média Móvel", "modulo": "MediaMovelStrategy", "arquivo": "estrategias.media_movel"},
    "mean_reversion": {"nome": "Reversão à Média", "modulo": "MeanReversionStrategy", "arquivo": "estrategias.mean_reversion"},
    "sr": {"nome": "Suporte/Resistência", "modulo": "SuporteResistenciaStrategy", "arquivo": "estrategias.suporte_resistencia"},
    "multi_tf": {"nome": "Multi-Timeframe", "modulo": "MultiTimeframeStrategy", "arquivo": "estrategias.multi_timeframe"},
    "scalping": {"nome": "Scalping", "modulo": "ScalpingStrategy", "arquivo": "estrategias.scalping"},
}

_relatorios_cache = {}


def _importar_estrategia(chave: str):
    info = estrategias_disponiveis[chave]
    mod = __import__(info["arquivo"], fromlist=[info["modulo"]])
    return getattr(mod, info["modulo"])


def _criar_estrategia(chave: str, saldo: float = 1000, quantidade: float = 0.1, **kwargs):
    cls = _importar_estrategia(chave)
    return cls(symbol="SIMULADO", saldo_inicial=saldo, quantidade_por_trade=quantidade, **kwargs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="TradeSimulado", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ─────────────────────────────── Rotas ───────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "estrategias": estrategias_disponiveis,
    })


@app.get("/api/estrategias")
async def listar_estrategias():
    return {
        k: {"nome": v["nome"]}
        for k, v in estrategias_disponiveis.items()
    }


@app.post("/api/backtest/executar")
async def executar_backtest_api(
    estrategia: str = Form(...),
    saldo: float = Form(1000),
    quantidade: float = Form(0.1),
    n_candles: int = Form(500),
    preco_inicial: float = Form(600),
    tipo_dado: str = Form("tendencia"),
    stop_loss: float = Form(0.02),
    take_profit: float = Form(0.04),
):
    try:
        cls = _importar_estrategia(estrategia)
        est = cls(
            symbol="SIMULADO",
            saldo_inicial=saldo,
            quantidade_por_trade=quantidade,
            stop_loss_percent=stop_loss,
            take_profit_percent=take_profit,
        )

        if tipo_dado == "sintetico":
            candles = gerar_dados_sinteticos(precos_inicial=preco_inicial, n_candles=n_candles)
        else:
            candles = gerar_tendencia_com_mudancas(precos_inicial=preco_inicial, n_candles=n_candles)

        inicio = time.time()
        relatorio = executar_backtest(est, candles)
        tempo = round(time.time() - inicio, 3)

        trades = []
        for t in est.trades[-50:]:
            ts = t["timestamp"]
            trades.append({
                "tipo": t["tipo"],
                "preco": round(t["preco"], 2),
                "quantidade": t["quantidade"],
                "timestamp": ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts),
                "motivo": t.get("motivo", ""),
            })

        resultado = {
            "estrategia": estrategias_disponiveis[estrategia]["nome"],
            "tempo_execucao": tempo,
            "candles": n_candles,
            "total_trades": relatorio["total_trades"],
            "lucro_usdt": relatorio["lucro_usdt"],
            "retorno_percentual": relatorio["retorno_percentual"],
            "taxa_acerto": relatorio["taxa_acerto"],
            "saldo_final": relatorio["saldo_final_usdt"],
            "portfolio": relatorio["valor_total_portfolio"],
            "trades": trades,
        }

        rid = datetime.now().strftime("%Y%m%d%H%M%S%f")
        _relatorios_cache[rid] = resultado

        return JSONResponse({"ok": True, "resultado": resultado, "id": rid})

    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "erro": str(e), "detalhe": traceback.format_exc()}, status_code=400)


@app.post("/api/backtest/comparar")
async def comparar_backtest_api(
    estrategias_lista: str = Form(...),
    saldo: float = Form(1000),
    quantidade: float = Form(0.1),
    n_candles: int = Form(500),
    preco_inicial: float = Form(600),
):
    try:
        chaves = [e.strip() for e in estrategias_lista.split(",") if e.strip()]

        def fabrica(chave):
            def fn():
                cls = _importar_estrategia(chave)
                return cls(symbol="SIMULADO", saldo_inicial=saldo, quantidade_por_trade=quantidade)
            return fn

        candles = gerar_tendencia_com_mudancas(precos_inicial=preco_inicial, n_candles=n_candles)

        pares = [(estrategias_disponiveis[c]["nome"], fabrica(c)) for c in chaves]
        resultados = comparar_estrategias(pares, candles)

        dados = []
        for r in resultados:
            dados.append({
                "estrategia": r["estrategia"],
                "trades": r["total_trades"],
                "lucro": r["lucro_usdt"],
                "retorno": r["retorno_percentual"],
                "acerto": r["taxa_acerto"],
                "saldo": r["saldo_final_usdt"],
            })

        return JSONResponse({"ok": True, "resultados": dados})

    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "erro": str(e), "detalhe": traceback.format_exc()}, status_code=400)


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_page(request: Request):
    return templates.TemplateResponse("backtest.html", {
        "request": request,
        "estrategias": estrategias_disponiveis,
    })


@app.get("/relatorio/{rid}", response_class=HTMLResponse)
async def relatorio_page(request: Request, rid: str):
    dados = _relatorios_cache.get(rid)
    if not dados:
        return HTMLResponse("Relatório não encontrado", status_code=404)
    return templates.TemplateResponse("relatorio.html", {
        "request": request,
        "dados": dados,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
