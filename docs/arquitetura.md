# Arquitetura

## Visão Geral

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py (CLI)                        │
│                                                             │
│  argparse → args (symbol, strategy, saldo, --live, etc.)    │
│       ↓                                                     │
│  criar_estrategia() → EstrategiaBase (ou subclasse)         │
│       ↓                                                     │
│  BinanceSocketManager → WebSocket kline stream              │
│       ↓                                                     │
│  processar_candle() → estrategia.processar_preco()          │
│       ↓                                                     │
│  executar_compra/venda (simulado ou Binance API)            │
│       ↓                                                     │
│  EstadoPersistente.salvar() a cada 10 candles               │
│       ↓                                                     │
│  salvar_relatorio() no Ctrl+C                               │
└─────────────────────────────────────────────────────────────┘
```

## Fluxo de Dados (Live)

```
Binance WebSocket (kline 1m)
  ↓ JSON
processar_candle() em main.py
  ↓ extrai {open, high, low, close, volume, timestamp}
estrategia.processar_preco(preco, timestamp, high, low, volume)
  ↓
├── Atualiza historico_precos (deque, maxlen=2000)
├── Calcula indicadores (RSI, MACD, BB, ADX, etc.)
├── Verifica proteções: stop-loss, take-profit, trailing stop
├── Verifica filtros: tendência, volume, cooldown, candle confirmation
├── Gera sinais de compra/venda
└── Chama executar_compra() ou executar_venda()
     ↓
├── Modo simulado: atualiza saldo_usdt e posicao
└── Modo live: client.order_market_buy/sell() na Binance
     ↓
EstadoPersistente.salvar() → resultados/estado_simulacao.json
     ↓ (a cada 10 candles)
salvar_dados_live() → resultados/live_candles.json (gráfico web)
```

## Hierarquia de Classes

```
EstrategiaBase (ABC)
├── RSIStrategy
├── RSIAvancadoStrategy
├── MACDStrategy
├── BollingerBandsStrategy
├── ADXStrategy
├── CombinacaoStrategy
├── GridSpotStrategy
├── MediaMovelStrategy
├── MeanReversionStrategy
├── SuporteResistenciaStrategy
├── MultiTimeframeStrategy
└── ScalpingStrategy
```

## Componentes

### main.py — Ponto de Entrada CLI
- Parse de argumentos via argparse com fallback para variáveis de ambiente
- Factory `criar_estrategia()` para instanciar qualquer estratégia pelo nome
- Loop async principal: conecta WebSocket Binance, processa candles em tempo real
- Reconexão automática (5 tentativas com exponential backoff)
- Salva estado a cada 10 candles e relatório ao finalizar

### backtest.py — Motor de Backtest
- `gerar_dados_sinteticos()`: random walk com volatilidade e tendência
- `gerar_tendencia_com_mudancas()`: 3 fases (alta, lateral, baixa)
- `executar_backtest()`: itera candles, executa estratégia, coleta resultados
- `comparar_estrategias()`: executa múltiplas estratégias nos mesmos dados

### estrategias/base.py — Classe Base (EstrategiaBase)
- Estado compartilhado: saldo, posição, histórico de preços (deque 2000)
- Indicadores: RSI (Wilder), SMA, EMA, volatilidade
- Rate limiting: 10 ordens/segundo (apenas live mode)
- Proteções centralizadas: stop-loss, take-profit, trailing stop
- Execução de ordens: simulada (padrão) ou via Binance API (live)
- Relatórios: P&L, win rate, retorno %, DataFrame de trades

### utils/logger.py — Logging
- Formato: `[LEVEL] mensagem` (info) ou `[timestamp] [LEVEL] mensagem` (debug)
- Console + arquivo opcional (`logs/trade.log`)

### utils/estado.py — Persistência
- Salva/carrega estado em JSON (`resultados/estado_simulacao.json`)
- Campos: saldo, posição, trades (últimos 100), preços (últimos 1000), proteções

### web/app.py — Interface Web (FastAPI)
- Rotas: dashboard, backtest interativo, live trading, relatórios
- Subprocesso para live bot com log em tempo real
- Cache de relatórios em memória

## Tecnologias

| Biblioteca | Versão | Uso |
|---|---|---|
| python-binance | 1.0.19 | API REST + WebSocket Binance |
| pandas | >=2.1.0 | DataFrame para relatórios |
| python-dotenv | 1.0.0 | Config via .env |
| fastapi | >=0.115.0 | Web framework |
| uvicorn | >=0.34.0 | ASGI server |
| jinja2 | >=3.1.0 | Template engine |
| pytest | — | Testes |
| ruff | — | Linter/formatter |
