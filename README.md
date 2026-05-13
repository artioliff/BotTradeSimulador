# TradeSimulado

Simulador de trading automatizado para criptomoedas. Consome dados em tempo real da Binance via WebSocket, executa 12 estratégias em modo simulado (paper trading) ou real, com backtest offline e interface web.

## Funcionalidades

- **12 estratégias** — RSI, MACD, Bollinger, ADX, Combinação, Grid, Médias, Reversão, S/R, Multi-TF, Scalping, RSI Avançado
- **Paper trading** — modo simulado sem risco financeiro
- **Live mode** — ordens reais na Binance (mainnet ou testnet)
- **Backtest offline** — dados sintéticos com tendência e volatilidade configuráveis
- **Interface web** — FastAPI + Bootstrap 5 + TradingView Lightweight Charts
- **Proteções** — stop-loss, take-profit, trailing stop, cooldown, filtro de tendência
- **Persistência** — salva/restaura estado automaticamente (JSON)
- **Relatórios** — P&L, taxa de acerto, retorno %, detalhamento por trade

## Início Rápido

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar .env (copie .exemplo.env e preencha)
cp .exemplo.env .env

# Backtesting offline
python backtest.py

# Live trading (WebSocket)
python main.py --symbol BNBUSDT --strategy combinacao --saldo 100

# Interface web
python -m web.app

# Testes
python -m pytest tests/ -v
```

## Documentação

| Arquivo | Descrição |
|---|---|
| `docs/arquitetura.md` | Arquitetura, fluxo de dados, componentes |
| `docs/estrategias.md` | Todas as 12 estratégias com parâmetros |
| `docs/api.md` | Endpoints da API web |
| `docs/analise.md` | Análise original do projeto |
| `docs/futuras-implementacoes.md` | Melhorias planejadas e priorizadas |
| `docs/changelog.md` | Histórico de correções |

## Estrutura

```
TradeSimulado/
├── main.py              # CLI + WebSocket live loop
├── backtest.py          # Backtest offline com dados sintéticos
├── web/                 # FastAPI + templates + static
│   ├── app.py
│   └── templates/
├── estrategias/         # 12 estratégias de trading
│   ├── base.py          # Classe base abstrata
│   ├── rsi.py
│   └── ...
├── utils/               # Logger + persistência de estado
├── tests/               # 45 testes (pytest)
└── docs/                # Documentação
```

## Requisitos

- Python 3.12+
- Conta Binance (para live mode)
- Dependências em `requirements.txt`
