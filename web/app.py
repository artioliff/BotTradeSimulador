import os
import json
import time
import asyncio
import subprocess
import signal
import sys
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

_live_process = None
_live_log_path = None


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
        for t in est.trades[-200:]:
            ts = t["timestamp"]
            trades.append({
                "tipo": t["tipo"],
                "preco": round(t["preco"], 2),
                "quantidade": t["quantidade"],
                "timestamp": ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts),
                "motivo": t.get("motivo", ""),
                "rsi": t.get("rsi"),
                "macd": t.get("macd"),
            })

        candle_data = []
        for c in candles[-300:]:
            ts = c["timestamp"]
            candle_data.append({
                "time": int(ts.timestamp()) if hasattr(ts, "timestamp") else 0,
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c["volume"],
            })

        trade_markers = []
        for t in est.trades:
            ts = t["timestamp"]
            trade_markers.append({
                "time": int(ts.timestamp()) if hasattr(ts, "timestamp") else 0,
                "position": "aboveBar" if t["tipo"] == "SELL" else "belowBar",
                "color": "#ef4444" if t["tipo"] == "SELL" else "#22c55e",
                "shape": "arrowDown" if t["tipo"] == "SELL" else "arrowUp",
                "text": f"{'V' if t['tipo']=='SELL' else 'C'} ${t['preco']:.2f}",
                "size": 2,
            })

        sl_tp_levels = []
        for i in range(0, len(trades)):
            t = trades[i]
            if t["tipo"] == "BUY" and i + 1 < len(trades):
                preco_compra = t["preco"]
                sl = round(preco_compra * (1 - stop_loss), 2)
                tp = round(preco_compra * (1 + take_profit), 2)
                saida = next((x for x in trades[i+1:] if x["tipo"] == "SELL"), None)
                if saida:
                    sl_tp_levels.append({
                        "buy_time": t["timestamp"],
                        "sell_time": saida["timestamp"],
                        "buy_price": preco_compra,
                        "sell_price": saida["preco"],
                        "stop_loss": sl,
                        "take_profit": tp,
                    })

        resultado = {
            "estrategia": estrategias_disponiveis[estrategia]["nome"],
            "tempo_execucao": tempo,
            "candles": n_candles,
            "total_trades": relatorio.get("total_trades", 0),
            "lucro_usdt": relatorio.get("lucro_usdt", 0),
            "retorno_percentual": relatorio.get("retorno_percentual", 0),
            "taxa_acerto": relatorio.get("taxa_acerto", 0),
            "saldo_final": relatorio.get("saldo_final_usdt", saldo),
            "portfolio": relatorio.get("valor_total_portfolio", saldo),
            "trades": trades,
            "candle_data": candle_data,
            "trade_markers": trade_markers,
            "sl_tp_levels": sl_tp_levels,
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


# ─────────────────────────────── Live Trading ───────────────────────────────

@app.get("/live", response_class=HTMLResponse)
async def live_page(request: Request):
    return templates.TemplateResponse("live.html", {
        "request": request,
        "estrategias": estrategias_disponiveis,
    })


@app.post("/api/live/iniciar")
async def live_iniciar(
    symbol: str = Form(...),
    estrategia: str = Form(...),
    saldo: float = Form(100),
    quantidade: float = Form(0.01),
    interval: str = Form("1m"),
    live_mode: bool = Form(False),
    testnet: bool = Form(False),
):
    global _live_process, _live_log_path

    if _live_process and _live_process.poll() is None:
        return JSONResponse({"ok": False, "erro": "Bot ja esta em execucao"})

    cmd = [
        sys.executable, str(BASE_DIR.parent / "main.py"),
        "--symbol", symbol,
        "--strategy", estrategia,
        "--saldo", str(saldo),
        "--quantidade", str(quantidade),
        "--interval", interval,
    ]
    if live_mode:
        cmd.append("--live")
    if testnet:
        cmd.append("--testnet")

    os.makedirs(str(BASE_DIR.parent / "logs"), exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _live_log_path = str(BASE_DIR.parent / "logs" / f"live_{timestamp}.log")
    log_file = open(_live_log_path, "w", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    _live_process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(BASE_DIR.parent),
        text=True,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    log_file.close()

    return JSONResponse({"ok": True, "pid": _live_process.pid, "log": _live_log_path})


@app.post("/api/live/parar")
async def live_parar():
    global _live_process

    if not _live_process or _live_process.poll() is not None:
        return JSONResponse({"ok": False, "erro": "Bot nao esta em execucao"})

    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(_live_process.pid)],
                           capture_output=True, timeout=5)
        else:
            _live_process.send_signal(signal.SIGTERM)
            _live_process.wait(timeout=5)
    except Exception:
        if _live_process.poll() is None:
            _live_process.kill()

    _live_process = None
    return JSONResponse({"ok": True, "mensagem": "Bot parado"})


@app.get("/api/live/status")
async def live_status():
    global _live_process

    running = _live_process is not None and _live_process.poll() is None
    linhas = []
    if _live_log_path and os.path.exists(_live_log_path):
        try:
            with open(_live_log_path, "r", encoding="utf-8") as f:
                todas = f.readlines()
                linhas = todas[-100:]
        except Exception:
            pass

    return JSONResponse({"ok": True, "running": running, "log": linhas, "log_path": _live_log_path})


@app.get("/api/live/candles")
async def live_candles():
    candles_path = BASE_DIR.parent / "resultados" / "live_candles.json"
    if not candles_path.exists():
        return JSONResponse({"ok": True, "candles": [], "trades": []})
    try:
        with open(str(candles_path), "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse({"ok": True, "candles": data.get("candles", []), "trades": data.get("trades", [])})
    except Exception:
        return JSONResponse({"ok": True, "candles": [], "trades": []})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
