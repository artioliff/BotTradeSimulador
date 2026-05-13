# API Web

Interface web FastAPI. Iniciar com:

```bash
python -m web.app
# Servidor em http://localhost:8000
```

## Páginas

### `GET /`
Dashboard com cards de todas as 12 estratégias e ações rápidas.

### `GET /backtest`
Interface completa de backtesting:
- Formulário de parâmetros (estratégia, saldo, candles, stop/take)
- Comparação entre estratégias
- Gráfico de velas (TradingView Lightweight Charts) com marcadores de compra/venda
- Tabela de trades ordenável
- Linhas de stop-loss e take-profit no gráfico

### `GET /live`
Painel de controle do bot ao vivo:
- Formulário de configuração (símbolo, estratégia, saldo, intervalo)
- Botão iniciar/parar
- Gráfico de velas em tempo real
- Log do bot com polling a cada 2s

### `GET /relatorio/{rid}`
Detalhes de um backtest executado anteriormente.

---

## Endpoints REST

### `GET /api/estrategias`
Lista todas as estratégias disponíveis.

**Resposta:**
```json
{
  "rsi": { "nome": "RSI" },
  "combinacao": { "nome": "Combinação" },
  ...
}
```

---

### `POST /api/backtest/executar`
Executa backtest de uma estratégia.

**Parâmetros (form):**

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `estrategia` | string | — | Nome da estratégia |
| `saldo` | float | 1000 | Saldo inicial USDT |
| `quantidade` | float | 0.1 | Quantidade por trade |
| `n_candles` | int | 500 | Número de candles |
| `preco_inicial` | float | 600 | Preço inicial |
| `tipo_dado` | string | "tendencia" | "sintetico" ou "tendencia" |
| `stop_loss` | float | 0.02 | Stop-loss % |
| `take_profit` | float | 0.04 | Take-profit % |

**Resposta:**
```json
{
  "ok": true,
  "resultado": {
    "estrategia": "Combinação",
    "total_trades": 42,
    "lucro_usdt": 150.50,
    "retorno_percentual": 15.05,
    "taxa_acerto": 64.3,
    "saldo_final": 1150.50,
    "portfolio": 1150.50,
    "candle_data": [ { "time": 1700000000, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000 } ],
    "trade_markers": [ { "time": 1700000000, "position": "belowBar", "color": "#22c55e", "shape": "arrowUp", "text": "C $100.50" } ],
    "trades": [ { "tipo": "BUY", "preco": 100.50, "quantidade": 0.1, "timestamp": "2024-01-01 12:00" } ]
  },
  "id": "20240101120000000000"
}
```

---

### `POST /api/backtest/comparar`
Compara múltiplas estratégias no mesmo conjunto de dados.

**Parâmetros (form):**

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `estrategias_lista` | string | — | Separado por vírgulas: "rsi,macd,bollinger" |
| `saldo` | float | 1000 | Saldo inicial |
| `n_candles` | int | 500 | Candles |
| `preco_inicial` | float | 600 | Preço inicial |

---

### `POST /api/live/iniciar`
Inicia o bot ao vivo como subprocesso.

**Parâmetros (form):**

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `symbol` | string | — | Par (ex: BNBUSDT) |
| `estrategia` | string | — | Nome da estratégia |
| `saldo` | float | 100 | Saldo inicial |
| `quantidade` | float | 0.01 | Quantidade por trade |
| `interval` | string | "1m" | Intervalo de candles |
| `live_mode` | bool | false | Ordens reais |
| `testnet` | bool | false | Usar Testnet |

---

### `POST /api/live/parar`
Para o bot ao vivo. Envia SIGTERM (Linux) ou taskkill (Windows).

---

### `GET /api/live/status`
Status do bot ao vivo.

**Resposta:**
```json
{
  "ok": true,
  "running": true,
  "log": ["[INFO] Cliente Mainnet\n", ...],
  "log_path": "logs/live_20240101_120000.log"
}
```

---

### `GET /api/live/candles`
Dados do gráfico em tempo real.

**Resposta:**
```json
{
  "ok": true,
  "candles": [
    { "time": 1700000000, "open": 600, "high": 601, "low": 599, "close": 600.5, "volume": 1000 }
  ],
  "trades": [
    { "time": 1700000000, "tipo": "BUY", "preco": 600.5 }
  ]
}
```
