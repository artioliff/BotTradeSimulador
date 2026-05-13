# Estratégias de Trading

## Visão Geral

12 estratégias implementadas, cada uma em arquivo próprio dentro de `estrategias/`. Todas herdam de `EstrategiaBase` e implementam:
- `__init__()` — parâmetros configuráveis
- `processar_preco()` — lógica principal por candle
- `reset()` — limpa estado
- `get_configuracao()` — retorna parâmetros atuais

---

## 1. RSI — `rsi.py` (`RSIStrategy`)

**Tipo:** Mean Reversion

Compra quando RSI entra em sobrevenda (≤ 30), vende quando entra em sobrecompra (≥ 70).

| Parâmetro | Default | Descrição |
|---|---|---|
| `periodo` | 14 | Período do RSI |
| `limite_inferior` | 30 | Sobrevenda |
| `limite_superior` | 70 | Sobrecompra |
| `stop_loss_percent` | 0.02 | Stop-loss 2% |
| `take_profit_percent` | 0.03 | Take-profit 3% |
| `trailing_stop_percent` | 0.01 | Trailing stop 1% |
| `max_perdas_consecutivas` | 5 | Cooldown após N perdas |
| `cooldown_periods` | 10 | Candles de pausa |
| `usar_filtro_tendencia` | false | Filtro EMA9/EMA21 |
| `usar_filtro_volume` | false | Volume > 70% da média 20 |
| `usar_saida_gradual` | false | Vende 25%/50%/100% em ganhos |
| `percentual_por_trade` | null | % do saldo por trade |

---

## 2. RSI Avançado — `rsi_avancado.py` (`RSIAvancadoStrategy`)

**Tipo:** Divergência + Tendência

RSI com detecção de divergências bull/bear, filtro de tendência com EMAs múltiplas e sistema de pesos para sinais.

| Parâmetro | Default | Descrição |
|---|---|---|
| `periodo` | 14 | Período do RSI |
| `usar_divergencia` | true | Detecta divergências preço/RSI |
| `usar_filtro_tendencia` | true | Filtro EMA9/EMA21/SMA200 |
| `usar_ema_multipla` | true | EMAs 9/21 para tendência |
| `periodo_tendencia` | 200 | SMA para tendência longa |

Sistema de pesos: divergência = peso 2, RSI = peso 1, tendência = peso 0.5.

---

## 3. MACD — `macd.py` (`MACDStrategy`)

**Tipo:** Trend Following

Compra quando MACD cruza acima da linha de sinal, vende quando cruza abaixo.

| Parâmetro | Default | Descrição |
|---|---|---|
| `fast_period` | 12 | EMA rápida |
| `slow_period` | 26 | EMA lenta |
| `signal_period` | 9 | EMA da linha MACD |

---

## 4. Bollinger Bands — `bollinger.py` (`BollingerBandsStrategy`)

**Tipo:** Mean Reversion

Compra quando preço toca a banda inferior, vende na banda superior ou ao retornar à média.

| Parâmetro | Default | Descrição |
|---|---|---|
| `periodo` | 20 | Período das bandas |
| `desvios` | 2 | Desvios padrão |
| `banda_min_largura` | 0.02 | Largura mínima (2%) |
| `banda_max_largura` | 0.10 | Largura máxima (10%) |
| `vender_na_media` | false | Vende parcial na média |
| `usar_confirmacao_candle` | true | Aguarda fechamento do candle |
| `usar_filtro_tendencia` | true | Não compra em tendência forte |

---

## 5. ADX — `adx.py` (`ADXStrategy`)

**Tipo:** Trend Following

Opera na direção da tendência quando ADX > 25. Compra se +DI > -DI, vende se -DI > +DI.

| Parâmetro | Default | Descrição |
|---|---|---|
| `periodo` | 14 | Período ADX (Wilder) |
| `limiar_tendencia` | 25 | Mínimo para considerar tendência |
| `usar_filtro_volume` | false | Filtro adicional de volume |

Duplo smoothing Wilder: primeiro em +DM/-DM/TR, segundo no DX para gerar ADX.

---

## 6. Combinação — `combinacao.py` (`CombinacaoStrategy`)

**Tipo:** Multi-Indicador

Votação ponderada entre RSI + MACD + Bollinger. Mínimo de 2 indicadores concordando para executar.

| Parâmetro | Default | Descrição |
|---|---|---|
| `periodo_rsi` | 14 | Período RSI |
| `limite_rsi_inf/sup` | 30/70 | Sobrevenda/sobrecompra |
| `macd_fast/slow/signal` | 12/26/9 | Parâmetros MACD |
| `bb_periodo` / `bb_desvios` | 20/2 | Parâmetros Bollinger |
| `peso_rsi/macd/bb` | 1/1.5/1 | Pesos dos indicadores |
| `min_concordancia` | 2 | Mínimo de indicadores concordando |

---

## 7. Grid Spot — `grid_spot.py` (`GridSpotStrategy`)

**Tipo:** Grid Trading

Cria grades de compra e venda em torno do preço atual. Opera em mercados laterais.

| Parâmetro | Default | Descrição |
|---|---|---|
| `num_grids` | 10 | Número total de grids |
| `spacing_percent` | 0.01 | Espaçamento entre grids (1%) |
| `max_grids_ativos` | 5 | Máximo de ordens simultâneas |
| `recomprar_apos_venda` | true | Reutiliza grid após venda |

---

## 8. Média Móvel — `media_movel.py` (`MediaMovelStrategy`)

**Tipo:** Trend Following (Simples)

Compra no cruzamento da SMA curta acima da SMA longa, vende no cruzamento inverso.

| Parâmetro | Default | Descrição |
|---|---|---|
| `periodo_curto` | 7 | SMA rápida |
| `periodo_longo` | 21 | SMA lenta |

Sem proteções (stop/take = 0).

---

## 9. Mean Reversion — `mean_reversion.py` (`MeanReversionStrategy`)

**Tipo:** Mean Reversion

Compra quando preço desvia X% abaixo da SMA, vende quando desvia X% acima ou retorna à média.

| Parâmetro | Default | Descrição |
|---|---|---|
| `periodo` | 20 | SMA de referência |
| `limiar` | 0.02 | Desvio mínimo (2%) |

---

## 10. Suporte/Resistência — `suporte_resistencia.py` (`SuporteResistenciaStrategy`)

**Tipo:** Níveis

Detecta mínimos (suportes) e máximos (resistências) locais nos últimos N candles. Compra em suporte, vende em resistência.

| Parâmetro | Default | Descrição |
|---|---|---|
| `lookback` | 100 | Candles para análise |
| `sensibilidade` | 0.005 | Tolerância (0.5%) |

Cache: recalcula níveis a cada 10 candles para performance.

---

## 11. Multi-Timeframe — `multi_timeframe.py` (`MultiTimeframeStrategy`)

**Tipo:** Multi-Timeframe

Calcula SMA curta vs longa para cada timeframe configurado. Decisão por maioria.

| Parâmetro | Default | Descrição |
|---|---|---|
| `periodos` | [5, 15, 60] | Timeframes em candles |

---

## 12. Scalping — `scalping.py` (`ScalpingStrategy`)

**Tipo:** Momentum

Opera movimentos rápidos com take-profit de 0.3% e stop-loss de 0.15%.

| Parâmetro | Default | Descrição |
|---|---|---|
| `lookback` | 10 | Período para momentum |
| `min_variacao` | 0.001 | Variação mínima (0.1%) |
