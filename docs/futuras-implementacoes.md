# Futuras Implementações

Prioridade: 🔴 Crítica → 🟡 Alta → 🟢 Média → 🔵 Baixa

---

## 🔴 Críticas

### R1 — Regenerar chaves da Binance expostas
**Arquivo:** `.env`
**Risco:** Chave `Hhla9Vz...` e secret `7xK2IS...` em texto puro. Se já commitadas, estão no histórico do git.
**Ação:** Regenerar imediatamente no painel da Binance. Verificar `git log --all -- .env`.

### R2 — Testes para todas as estratégias
**Arquivos:** `tests/`
**Gap:** 10 de 12 estratégias sem nenhum teste (apenas RSI e Combinação testados).
**Mínimo por estratégia:** `test_init`, `test_sinais_com_dados_suficientes`, `test_reset`, `test_get_configuracao`.

---

## 🟡 Alta

### R3 — Extrair templates para usar `base.html`
**Arquivos:** `web/templates/live.html`, `backtest.html`
**Problema:** ~700 linhas de HTML duplicado (navbar, head, scripts). Mudanças no layout precisam ser replicadas em 3 arquivos.
**Solução:** Fazer `live.html` e `backtest.html` estenderem `base.html`, movendo apenas o conteúdo específico para blocks.

### R4 — Rate limiter async
**Arquivo:** `estrategias/base.py:171`
**Problema:** `time.sleep(0.1)` bloqueia o event loop async por até 2 segundos.
**Solução:** Substituir por `asyncio.sleep()` ou usar abordagem não-bloqueante.

### R5 — Guard `AttributeError` no `_verificar_stop_take_trailing()`
**Arquivo:** `estrategias/base.py:187`
**Problema:** `self.preco_compra_medio` pode não existir em estratégias que não o definem.
**Solução:** Usar `getattr(self, 'preco_compra_medio', 0.0)` com fallback.

### R6 — Limitar `_relatorios_cache`
**Arquivo:** `web/app.py:43`
**Problema:** Cache de relatórios em memória sem limite. Vaza memória.
**Solução:** Adicionar LRU (ex: `cachetools.LRUCache(maxsize=100)`) ou TTL de expiração.

### R7 — Rate limiting na API de backtest
**Arquivo:** `web/app.py:97`
**Problema:** Endpoint sem proteção contra uso excessivo.
**Solução:** Adicionar `slowapi` ou middleware de rate limiting.

### R8 — Testes para a API web
**Arquivo:** `tests/` (novo: `test_web.py`)
**Gap:** Nenhum teste para os endpoints FastAPI.
**Solução:** Usar `TestClient` do FastAPI para testar rotas.

---

## 🟢 Média

### R9 — Incremental RSI/EMA
**Arquivo:** `estrategias/base.py:79-133`
**Problema:** Indicadores recalculados do zero a cada candle (O(n) por chamada).
**Solução:** Armazenar média de ganhos/perdas anterior e atualizar incrementalmente.

### R10 — Validação de input no subprocesso
**Arquivo:** `web/app.py:292-301`
**Problema:** Argumentos passados ao subprocesso sem validação.
**Solução:** Whitelist de símbolos/estratégias válidos antes de passar ao `Popen`.

### R11 — Graceful shutdown no Windows
**Arquivo:** `web/app.py:335-338`
**Problema:** `taskkill /F /T` mata processo sem cleanup.
**Solução:** Usar `GenerateConsoleCtrlEvent` para desligamento gracioso.

### R12 — Banco de dados para persistência
**Arquivo:** `utils/estado.py`
**Problema:** Estado salvo em JSON. Sem atomicidade, sem concorrência.
**Solução:** SQLite para dados locais, PostgreSQL para produção.

### R13 — Cache de backtest por hash de parâmetros
**Arquivo:** `web/app.py:97`
**Problema:** Cada backtest é executado do zero, mesmo com parâmetros idênticos.
**Solução:** Cachear resultados por hash dos parâmetros de entrada.

### R14 — Padronizar nomenclatura (português vs inglês)
**Arquivos:** Todas as estratégias
**Problema:** Identificadores misturam PT (`saldo_usdt`, `preco_compra_medio`) e EN (`stop_loss_percent`, `take_profit_percent`).
**Solução:** Escolher inglês como padrão e refatorar.

---

## 🔵 Baixa

### R15 — Mover JS inline para `app.js`
**Arquivos:** `web/templates/*.html`, `web/static/js/app.js`
**Problema:** Todo JavaScript está inline nos templates.
**Solução:** Extrair funções compartilhadas para `app.js`.

### R16 — Indicadores em módulo separado
**Arquivos:** `estrategias/` (novo: `indicadores.py`)
**Problema:** Cálculo de RSI, MACD, BB duplicado em várias estratégias.
**Solução:** Extrair para módulo compartilhado `estrategias/indicadores.py`.

### R17 — Hierarquia de exceções customizadas
**Arquivo:** `estrategias/` (novo: `exceptions.py`)
**Problema:** Todo erro usa `Exception` genérico.
**Solução:** Criar `TradeSimuladoError`, `SaldoInsuficienteError`, `PosicaoInsuficienteError`, etc.

### R18 — `random.seed()` global no backtest
**Arquivo:** `backtest.py:33, 67`
**Problema:** `random.seed()` afeta estado global do módulo `random`.
**Solução:** Usar instância própria de `random.Random(seed)`.

### R19 — Pre-commit hooks
**Arquivo:** Novo `.pre-commit-config.yaml`
**Problema:** Sem validação automática antes de commits.
**Solução:** Ruff + pytest como hooks pre-commit.

### R20 — Docker
**Arquivo:** Novo `Dockerfile`
**Problema:** Sem ambiente padronizado para execução.
**Solução:** Dockerfile multi-stage com Python 3.12 + dependências.

### R21 — HTTPS
**Arquivo:** `web/app.py:381`
**Problema:** Servidor HTTP sem criptografia.
**Solução:** Adicionar SSL via uvicorn ou proxy reverso (nginx).

### R22 — Exportar trades como CSV
**Arquivo:** `web/templates/backtest.html`
**Problema:** Trades visíveis apenas na tabela HTML.
**Solução:** Botão "Exportar CSV" que baixa os trades.
