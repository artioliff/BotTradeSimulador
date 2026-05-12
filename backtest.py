"""
Backtesting offline para estratégias de trading.
Gera dados sintéticos ou carrega CSV, executa a estratégia candle a candle,
e produz relatório completo de performance.
"""
import random
import math
from datetime import datetime, timedelta
from collections import deque
from typing import Callable


def gerar_dados_sinteticos(
    precos_inicial: float = 600.0,
    n_candles: int = 1000,
    volatilidade: float = 0.005,
    tendencia: float = 0.0001,
    seed: int = 42
):
    """
    Gera dados OHLCV sintéticos para backtesting.

    Args:
        precos_inicial: Preço inicial
        n_candles: Número de candles a gerar
        volatilidade: Volatilidade diária (ex: 0.005 = 0.5%)
        tendencia: Tendência por candle (ex: 0.0001 = 0.01%)
        seed: Semente aleatória para reprodutibilidade

    Returns:
        list[dict]: Lista de candles com keys: timestamp, open, high, low, close, volume
    """
    random.seed(seed)
    candles = []
    preco = precos_inicial
    agora = datetime.now()

    for i in range(n_candles):
        open_price = preco
        variacao = random.gauss(tendencia, volatilidade)
        close_price = preco * (1 + variacao)

        high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, volatilidade * 0.5)))
        low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, volatilidade * 0.5)))
        volume = random.uniform(100, 1000)

        candles.append({
            'timestamp': agora - timedelta(minutes=(n_candles - i)),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': round(volume, 2)
        })

        preco = close_price

    return candles


def gerar_tendencia_com_mudancas(
    precos_inicial: float = 600.0,
    n_candles: int = 1000,
    seed: int = 42
):
    """Gera dados com 3 fases: alta, lateral, baixa"""
    random.seed(seed)
    candles = []
    preco = precos_inicial
    agora = datetime.now()

    fases = [
        (0, n_candles // 3, 0.0003, 0.004),     # alta
        (n_candles // 3, 2 * n_candles // 3, 0.0, 0.003),   # lateral
        (2 * n_candles // 3, n_candles, -0.0003, 0.005),    # baixa
    ]

    for i in range(n_candles):
        open_price = preco
        tendencia, volatilidade = 0, 0.003
        for inicio, fim, t, v in fases:
            if inicio <= i < fim:
                tendencia, volatilidade = t, v
                break

        variacao = random.gauss(tendencia, volatilidade)
        close_price = preco * (1 + variacao)
        high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, volatilidade * 0.5)))
        low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, volatilidade * 0.5)))
        volume = random.uniform(100, 1000)

        candles.append({
            'timestamp': agora - timedelta(minutes=(n_candles - i)),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': round(volume, 2)
        })
        preco = close_price

    return candles


def executar_backtest(estrategia, candles: list[dict], verbose: bool = False):
    """
    Executa uma estratégia contra dados históricos.

    Args:
        estrategia: Instância de EstrategiaBase
        candles: Lista de dicts com timestamp, open, high, low, close, volume
        verbose: Se True, imprime trades conforme ocorrem

    Returns:
        dict: Relatório completo de performance
    """
    estrategia.reset()
    trades_executados = 0
    tempo_inicio = datetime.now()

    for i, candle in enumerate(candles):
        trades = estrategia.processar_preco(
            preco=candle['close'],
            timestamp=candle['timestamp'],
            high=candle['high'],
            low=candle['low'],
            volume=candle['volume']
        )

        if trades:
            trades_executados += len(trades)
            if verbose:
                for t in trades:
                    print(f"  TRADE: {t['tipo']} @ ${t['preco']:.2f} | {t.get('motivo', 'SINAL')}")

        if verbose and (i + 1) % 200 == 0:
            print(f"  [{i+1}/{len(candles)} candles] Trades: {trades_executados}")

    tempo_execucao = (datetime.now() - tempo_inicio).total_seconds()
    relatorio = estrategia.get_relatorio()
    relatorio['tempo_execucao'] = round(tempo_execucao, 3)
    relatorio['candles_processados'] = len(candles)
    relatorio['trades_por_candle'] = round(trades_executados / len(candles), 4) if candles else 0

    return relatorio


def comparar_estrategias(
    estrategias: list[tuple[str, Callable]],
    candles: list[dict],
    verbose: bool = False
):
    """
    Compara múltiplas estratégias nos mesmos dados.

    Args:
        estrategias: Lista de (nome, funcao_que_cria_instancia)
        candles: Dados históricos
        verbose: Log detalhado

    Returns:
        list[dict]: Relatórios de cada estratégia
    """
    resultados = []
    for nome, fabrica in estrategias:
        if verbose:
            print(f"\n=== Executando {nome} ===")
        est = fabrica()
        relatorio = executar_backtest(est, candles, verbose=verbose)
        relatorio['estrategia'] = nome
        resultados.append(relatorio)
        if verbose:
            print(f"  -> {nome}: {relatorio['total_trades']} trades, lucro=${relatorio['lucro_usdt']}, acerto={relatorio['taxa_acerto']}%")

    return resultados


def print_relatorio(relatorio: dict, nome: str = "") -> None:
    """Imprime relatório formatado no console"""
    titulo = f" RELATORIO {nome} " if nome else " RELATORIO "
    print(f"\n{'='*60}")
    print(f"{titulo:=^60}")
    print(f"{'='*60}")

    if relatorio.get('total_trades', 0) == 0:
        print("Nenhum trade executado.")
        return

    print(f"Candles: {relatorio.get('candles_processados', 'N/A')}")
    print(f"Tempo execução: {relatorio.get('tempo_execucao', 0):.2f}s")
    print(f"Total trades: {relatorio['total_trades']}")
    print(f"  Compras: {relatorio['total_compras']}")
    print(f"  Vendas: {relatorio['total_vendas']}")
    print(f"Total comprado: ${relatorio['total_comprado_usdt']:.2f}")
    print(f"Total vendido: ${relatorio['total_vendido_usdt']:.2f}")
    print(f"LUCRO: ${relatorio['lucro_usdt']:.2f}")
    print(f"Retorno: {relatorio['retorno_percentual']}%")
    print(f"Taxa acerto: {relatorio['taxa_acerto']}%")
    print(f"Saldo final: ${relatorio['saldo_final_usdt']:.2f}")
    print(f"Portfolio: ${relatorio['valor_total_portfolio']:.2f}")
    print(f"{'='*60}")


def run_example():
    """Executa exemplo completo de backtesting"""
    from estrategias import RSIStrategy, CombinacaoStrategy, BollingerBandsStrategy

    print("Gerando dados sintéticos...")
    candles = gerar_tendencia_com_mudancas(precos_inicial=600.0, n_candles=1000)

    estrategias = [
        ("RSI(14,30,70)", lambda: RSIStrategy(
            symbol="SIMULADO", periodo=14, limite_inferior=30, limite_superior=70,
            quantidade_por_trade=0.1, saldo_inicial=1000,
            stop_loss_percent=0.02, take_profit_percent=0.04)),
        ("Bollinger(20,2)", lambda: BollingerBandsStrategy(
            symbol="SIMULADO", periodo=20, desvios=2,
            quantidade_por_trade=0.1, saldo_inicial=1000,
            stop_loss_percent=0.02, take_profit_percent=0.04)),
        ("Combinacao", lambda: CombinacaoStrategy(
            symbol="SIMULADO", periodo_rsi=14, limite_rsi_inf=30, limite_rsi_sup=70,
            quantidade_por_trade=0.1, saldo_inicial=1000,
            stop_loss_percent=0.02, take_profit_percent=0.04)),
    ]

    resultados = comparar_estrategias(estrategias, candles, verbose=True)

    print(f"\n{'='*60}")
    print(f"{' RESUMO COMPARATIVO ':=^60}")
    print(f"{'='*60}")
    for r in sorted(resultados, key=lambda x: x['lucro_usdt'], reverse=True):
        lucro_str = f"+${r['lucro_usdt']:.2f}" if r['lucro_usdt'] >= 0 else f"-${abs(r['lucro_usdt']):.2f}"
        print(f"  {r['estrategia']:25s} | Trades: {r['total_trades']:3d} | Lucro: {lucro_str:>8s} | Acerto: {r['taxa_acerto']:5.1f}% | Ret: {r['retorno_percentual']:6.2f}%")


if __name__ == "__main__":
    run_example()
