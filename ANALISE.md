# TradeSimulado - Análise de Código

## Visão Geral do Projeto

Projeto de simulação de trading em tempo real que coleta dados da Binance via WebSocket e executa stratégies (RSI, Média Móvel, Grid Spot).

## Problemas Encontrados

### 🔴 Críticos (Segurança)

#### 1. API Keys Reais Expostas
**Arquivo:** `.env:2-3`

```
BINANCE_API_KEY=Hhla9Vz9P3bTTYkV2dAXyrUS6pFwaA24hMiXmRud64A4bdbeheKtekX7oKixtAoh
BINANCE_API_SECRET=7xK2IS97SGVseQlrSCUqu9qHVhgR7SzgeUVkEdJIx54gmqrbUDT9sRg3qlXtHNq8
```

**Risco:** Acesso completo à conta Binance.
**Correção:** Regenerar chaves imediatamente, adicionar `.env` ao `.gitignore`.

---

### 🐛 Bugs

#### 2. Grid Spot Não Reseta Correta e Completamente
**Arquivo:** `estrategias/grid_spot.py:99-110`

```python
def reset(self):
    super().reset()
    self.grids_calculados = False
    self.compras_executadas = []
    self.vendas_executadas = []
    if hasattr(self, 'niveis_compra'):
        for nivel in self.niveis_compra:  # BUG: apenas sinaliza como não executado
            nivel['executada'] = False   # mas não cria novos níveis
```

**Problema:** Após reset, os níveis antigos permanência em memória.
**Correção:** Recalcular grids ou usar `self.niveis_compra = []`.

#### 3. USE_TESTNET Ignorado
**Arquivo:** `main.py:139-144`

```python
if API_KEY and API_SECRET:
    client = Client(API_KEY, API_SECRET)
    print("Cliente autenticado com API Key")
else:
    client = Client()  # Sempre usa o que for passado, ignora USE_TESTNET
```

**Correção:** Verificar `os.getenv('USE_TESTNET') == 'true'` e usar `Client(testnet=True)`.

#### 4. Conflito take-profit / stop-loss
**Arquivo:** `estrategias/rsi.py:108-144`

```python
# Executa stop-loss primeiro (linha 111-125)
if perda_percentual <= -self.stop_loss_percent:
    trade = self.executar_venda(...)
    return ordens_executadas  # early return

# Depois take-profit (linha 130-144)
if lucro_percentual >= self.take_profit_percent:
    trade = self.executar_venda(...)
```

**Problema:** Se o preço oscilar entre stop-loss e take-profit na mesma vela, apenas stop-loss executa.
**Correção:** Usar OR em vez de verificações sequenciais, ou verificar qual é mais favorável.

---

### 🔄 Código Duplicado

#### 5. Cálculo RSI Repetido
**Arquivos:** `estrategias/rsi.py:50-80` e `estrategias/rsi_avancado.py:44-76`

Ambas as methods fazem exatamente o mesmo cálculo (Wilder smoothing):

```python
def calcular_rsi_wilder(self, precos):  # rsi.py
def calcular_rsi(self, precos):      # rsi_avancado.py
    # mesmo código
```

**Correção:** Mover para classe base `EstrategiaBase`.

#### 6. Detecção de Divergência Mal Implementada
**Arquivo:** `estrategias/rsi_avancado.py:78-117`

```python
# Usa min/max simples, não detecta pivôs locais
preco_min = min(precos_recentes)
preco_max = max(precos_recentes)

# Lógica de índices está incorreta
if idx_preco_min > idx_rsi_min and preco_min < precos_recentes[-1] and rsi_min > rsi_recentes[-1]:
    divergencia_alta = True
```

**Problemas:**
- Não detecta pivôs locais reais (apenas extremos)
- Flag de divergência fica true permanentemente sem reset
- Não considera força da divergência

---

### ⚠️ Lógicos / Arquitetura

#### 7. Sem Persistência de Estado

```python
# main.py:137-198
# Se programa fechar abruptamente:
# - self.em_posicao é perdido
# - self.preco_compra_medio é perdido
# - Histórico de preços é perdido
```

**Correção:** Salvar estado em JSON periodicamente.

#### 8. Sem Controle de Rate Limit

```python
# estratégias/base.py:126-159
# executar_compra() e executar_venda() não têm delays
# Binance pode bloquear por muitos requests
```

**Correção:** Adicionar `time.sleep()` entre ordens ou usar throttling.

#### 9. Sincronização com Conta Real Comentada

```python
# estrategias/base.py:136-138
# Opcional: sincroniza saldo real após compra
# self.sincronizar_saldo_apos_trade('BUY', preco, quantidade)  # comentado

# estrategias/base.py:153-155
# Opcional: sincroniza saldo real após venda
# self.sincronizar_saldo_apos_trade('SELL', preco, quantidade)  # comentado
```

**Problema:** Simulação nunca confere com saldo real.

#### 10. Ausência de Tratamento de Exceções Assíncronas

```python
# main.py:200-203
try:
    async with ts as tscm:
        while True:
            msg = await tscm.recv()
            processar_mensagem(msg)

except asyncio.CancelledError:
    print("\nParando coleta...")  # Só trata cancelamento
except KeyboardInterrupt:
    print("\nParando...")
# Não trata: ConnectionError, socket timeout, etc.
```

---

### 📋 Qualidade de Código

#### 11. Sem Tipagem (type hints)

```python
# Todas as funções/métodos não têm annotations
def processar_preco(self, preco, timestamp):
    # deveria ser: def processar_preco(self, preco: float, timestamp: datetime) -> list[dict]:
```

#### 12. Funções com Efeitos Colaterais Não Documentados

`RSIStrategy.processar_preco()` modifica estado interno E retorna valores, sem clareza.

#### 13. Histórico Cresce Infinitamente

```python
# estrategias/rsi.py:92
self.historico_precos.append(preco)
# Nunca remove preços antigos
# Memória vazará em execução contínua
```

**Correção:** Usar `collections.deque` com maxlen ou manter apenas últimos N itens.

---

## Recomendações de Correção (Prioridade)

| # | Severidade | Problema | Esforço |
|---|----------|---------|---------|
| 1 | 🔴 Crítico | Regenerar API Keys | Baixo |
| 2 | 🐛 Bug | Resolver bug grid_spot.reset() | Baixo |
| 3 | 🐛 Bug | Corrigir conflito TP/SL | Baixo |
| 4 | 🔄 Duplicado | Mover RSI para classe base | Médio |
| 5 | ⚠️ Lógico | Adicionar persistência JSON | Alto |
| 6 | ⚠️ Lógico | Adicionar rate limiting | Baixo |
| 7 | 🔄 Duplicado | Corrigir detecção divergência | Médio |