# TradeSimulado - Análise do Projeto

## Visão Geral

Simulador de trading que consome dados WebSocket da Binance em tempo real
e executa estratégias automatizadas. Construído em Python com `python-binance`,
`pandas` e `dotenv`.

## Estrutura

```
TradeSimulado/
├── main.py                    # CLI + loop principal com WebSocket
├── backtest.py                # Backtesting offline com dados sintéticos
├── requirements.txt
├── .env / .exemplo.env
├── .gitignore
├── ANALISE.md
├── estrategias/
│   ├── base.py                # Classe base EstrategiaBase
│   ├── rsi.py                 # RSI (refatorado)
│   ├── rsi_avancado.py        # RSI com divergências
│   ├── macd.py                # MACD (corrigido EMA seed + signal)
│   ├── bollinger.py           # Bandas de Bollinger
│   ├── adx.py                 # ADX (corrigido smoothing duplo)
│   ├── combinacao.py          # Combinação RSI+MACD+Bollinger
│   ├── grid_spot.py           # Grid Spot
│   ├── media_movel.py         # Cruzamento de médias
│   ├── mean_reversion.py      # Reversão à média
│   ├── suporte_resistencia.py # Suporte e Resistência
│   ├── multi_timeframe.py     # Multi-timeframe
│   └── scalping.py            # Scalping (corrigido)
├── tests/
│   ├── test_base.py           # 26 testes: RSI, EMA, trades, relatório
│   ├── test_rsi.py            # 5 testes: sinais RSI
│   ├── test_combinacao.py     # 8 testes: indicadores combinados
│   └── test_backtest.py       # 6 testes: dados sintéticos + execução
└── utils/
    ├── estado.py              # Persistência de estado JSON
    └── logger.py              # Configuração de logging
```

## Status das Correções

### 🔴 Críticos (corrigidos)

| Problema | Arquivo | Correção |
|---|---|---|
| API Keys expostas no .env | `.env` | `.gitignore` já ignora `.env`. Regenerar chaves se expostas. |
| Scalping sem init/reset/config | `scalping.py` | Adicionado `quantidade_comprada_total`, `preco_compra_medio`, `reset()`, `get_configuracao()` |
| ADX sem smoothing (era DX) | `adx.py` | Adicionado `_calcular_adx_suavizado()` com Wilder smoothing duplo |
| MACD sem get_configuracao() | `macd.py` | Adicionado |
| Multi-TF sem reset/get_configuracao | `multi_timeframe.py` | Adicionado |
| MACD `_calcular_ema_de_lista` inexistente | `macd.py` | Substituído por `_calcular_ema()` com histórico de valores MACD |
| Combinacao: deque não suporta slicing | `combinacao.py` | Convertido para list() antes de fatiar |

### 🟡 Médios (corrigidos)

| Problema | Arquivo | Correção |
|---|---|---|
| TP/SL/Trailing duplicado em 5 estratégias | `base.py`, `rsi.py`, `rsi_avancado.py`, `bollinger.py`, `combinacao.py`, `adx.py` | Extraído para `_verificar_stop_take_trailing()` na classe base |
| 4 estratégias sem proteções (stop/take) | `macd.py`, `mean_reversion.py`, `suporte_resistencia.py`, `multi_timeframe.py` | Adicionados parâmetros de proteção + chamada ao método base |
| MACD: EMA seed incorreta (`precos[0]`) | `macd.py` | Seed corrigida para `sum(precos[:periodo]) / periodo` |
| Média Móvel: vendia posição inteira | `media_movel.py` | Corrigido para `self.quantidade_por_trade` |
| Suporte/Resistência: O(n) por tick | `suporte_resistencia.py` | Cache de níveis, recalcula a cada 10 candles |
| RSI Avançado: EMA recalculada do zero | `rsi_avancado.py` | Usa `calcular_media_movel_exponencial()` da base |
| Combinação: EMA200 recalculada do zero | `combinacao.py` | Cache incremental da EMA200 |
| Bollinger: vendas múltiplas na média | `bollinger.py` | Cooldown de 5 candles na venda parcial |

### 🟢 Qualidade (corrigidos)

| Problema | Arquivo | Correção |
|---|---|---|
| Sem type hints em 6 arquivos | Todos | Type hints adicionados em todas as estratégias |
| Sem testes automatizados | `tests/` | 49 testes com unittest + pytest |
| Sem backtesting offline | `backtest.py` | Dados sintéticos + execução + comparativo |
| Persistência não integrada | `main.py` + `utils/estado.py` | Salva/restaura estado automaticamente |
| `print()` sem estrutura | `utils/logger.py` + `base.py` | Logging module com níveis e arquivo |
| main.py hardcoded | `main.py` | Argumentos CLI (--symbol, --strategy, --saldo, etc) |
| Sem linter/CI | `pyproject.toml` | Ruff configurado + script de teste |

## Estratégias

| Estratégia | Lógica | Proteções | Testes |
|---|---|---|---|
| **Combinação** | Votação RSI+MACD+Bollinger (≥2 indicadores) | TP/SL/Trailing/Cooldown | 8 testes |
| **RSI** | Compra em sobrevenda, vende em sobrecompra | TP/SL/Trailing/Cooldown/Filtros | 5 testes |
| **RSI Avançado** | RSI + divergências bull/bear + EMAs | TP/SL/Trailing/Cooldown | - |
| **Bollinger** | Reversão à média nas bandas | TP/SL/Trailing/Cooldown/Filtro largura | - |
| **ADX** | Segue tendência forte (ADX > 25) | TP/SL/Trailing | - |
| **MACD** | Cruzamento MACD/Signal | TP/SL/Trailing | - |
| **Grid Spot** | Grades de compra/venda | Stop-loss/Trailing | - |
| **Média Móvel** | Cruzamento SMA curta/longa | - | - |
| **Mean Reversion** | Desvio X% da média | TP/SL/Trailing | - |
| **S/R** | Min/max locais | TP/SL/Trailing | - |
| **Multi-TF** | Maioria entre N timeframes | TP/SL/Trailing | - |
| **Scalping** | Momentum rápido (0.3% take, 0.15% stop) | Take/Stop fixos | - |

## Como executar

```bash
# Live trading (WebSocket)
python main.py --symbol BNBUSDT --strategy combinacao --saldo 100

# Backtesting offline
python backtest.py

# Testes
python -m pytest tests/ -v

# Ajuda
python main.py --help
```
