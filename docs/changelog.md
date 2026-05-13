# Changelog

Todas as alterações relevantes neste projeto.

---

## [Sessão Atual] — 2026-05-13

### Corrigido

#### Críticos
- **`MultiTimeframeStrategy` sem `periodos` no `reset()`** — `EstrategiaBase.__init__()` chamava `self.reset()` polimórfico antes da subclasse definir `self.periodos`, causando `AttributeError`. Corrigido movendo `self.periodos` antes de `super().__init__()`.
- **`_verificar_rate_limit()` recursivo e bloqueante** — Função chamava a si mesma recursivamente em caso de rate limit, podendo estourar a stack. Também bloqueava o event loop async com `time.sleep()`. Corrigido: loop no lugar de recursão com máximo de 20 tentativas, e `live_mode` check para pular em modo simulado.
- **`RSIStrategy` sem parâmetro `debug`** — Factory em `main.py` passava `debug=debug` para todas as estratégias, mas `RSIStrategy.__init__()` não aceitava o parâmetro. Adicionado `debug=False` com repasse ao `super().__init__()`.

#### Médios
- **`time.sleep(2)` bloqueante no event loop async** — `main.py` tinha `time.sleep(2)` dentro de `async def main()`, bloqueando o event loop. Removido.
- **Buffer de stdout no subprocesso** — Log do bot ao vivo não aparecia na web porque stdout era bufferado. Adicionado `PYTHONUNBUFFERED=1` no environment do subprocesso.
- **`autoSize: true` quebrando `DOMContentLoaded`** — Lightweight Charts com `autoSize: true` lançava erro que propagava e impedia registro de event listeners. Substituído por altura fixa com fallback 400px + resize listener, e `try-catch` no `initChart()`.
- **Duplicata de funções JS** — Edições anteriores criaram duas definições de `iniciarPolling`, `pararPolling`, `initChart`, `atualizarChart` e `buscarCandles`. Removidas duplicatas, cada função passou a existir uma única vez.

---

## [Sessões Anteriores]

### Adicionado
- **12 estratégias de trading** implementadas
- **Motor de backtest** com dados sintéticos (random walk + tendência)
- **Interface web** FastAPI com Bootstrap 5 dark/light theme
- **Gráfico TradingView Lightweight Charts** no backtest
- **45 testes** com pytest (base, RSI, combinação, backtest)
- **Persistência de estado** em JSON com `EstadoPersistente`
- **Logger** estruturado com níveis e arquivo
- **Linter** Ruff configurado em `pyproject.toml`
- **CLI** com argparse e fallback para variáveis de ambiente

### Corrigido
- **Scalping sem `__init__`/`reset()`/`get_configuracao()`** — Adicionados método e parâmetros de estado
- **ADX sem duplo smoothing Wilder** — Adicionado `_calcular_adx_suavizado()`
- **MACD sem `get_configuracao()`** — Adicionado
- **Multi-TF sem `reset()`/`get_configuracao()`** — Adicionados
- **MACD EMA seed incorreta** — Corrigido de `precos[0]` para SMA dos primeiros N valores
- **Combinacao: deque sem suporte a slicing** — Convertido para `list()` antes de fatiar
- **Stop/take/trailing duplicado em 5 estratégias** — Extraído para `_verificar_stop_take_trailing()` na classe base
- **4 estratégias sem proteções** — Adicionados parâmetros de stop/take/trailing
- **Média Móvel vendia posição inteira** — Corrigido para `quantidade_por_trade`
- **Suporte/Resistência O(n) por tick** — Adicionado cache com recálculo a cada 10 candles
- **RSI Avançado EMA recalculada do zero** — Passou a usar método da classe base
- **Combinação EMA200 recalculada do zero** — Adicionado cache incremental
- **Bollinger múltiplas vendas na média** — Adicionado cooldown de 5 candles
- **Type hints ausentes** — Adicionados em todas as estratégias
