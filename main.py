import asyncio
import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
from binance import Client, AsyncClient, BinanceSocketManager
from utils.estado import EstadoPersistente
from utils.logger import setup_logger

load_dotenv()

log = setup_logger("TradeSimulado", debug=False, arquivo="trade.log")


def criar_estrategia(nome: str, symbol: str, saldo: float, quantidade: float, debug: bool):
    from estrategias import (
        RSIStrategy, RSIAvancadoStrategy, MACDStrategy, BollingerBandsStrategy,
        ADXStrategy, GridSpotStrategy, MediaMovelStrategy, MeanReversionStrategy,
        SuporteResistenciaStrategy, MultiTimeframeStrategy, ScalpingStrategy,
        CombinacaoStrategy
    )
    mapa = {
        "rsi": lambda: RSIStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade, debug=debug),
        "rsi_avancado": lambda: RSIAvancadoStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade, debug=debug),
        "macd": lambda: MACDStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade),
        "bollinger": lambda: BollingerBandsStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade, debug=debug),
        "adx": lambda: ADXStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade),
        "grid": lambda: GridSpotStrategy(symbol, saldo_inicial=saldo, quantidade_por_ordem=quantidade),
        "media_movel": lambda: MediaMovelStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade),
        "mean_reversion": lambda: MeanReversionStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade),
        "sr": lambda: SuporteResistenciaStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade),
        "multi_tf": lambda: MultiTimeframeStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade),
        "scalping": lambda: ScalpingStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade),
        "combinacao": lambda: CombinacaoStrategy(symbol, saldo_inicial=saldo, quantidade_por_trade=quantidade, debug=debug),
    }
    if nome not in mapa:
        log.error("Estrategia desconhecida: %s. Opcoes: %s", nome, ", ".join(sorted(mapa)))
        sys.exit(1)
    return mapa[nome]()


def parse_args():
    p = argparse.ArgumentParser(description="TradeSimulado - Trading Bot Simulator")
    p.add_argument("--symbol", default=os.getenv("SYMBOL", "BNBUSDT"), help="Par de trading (ex: BTCUSDT)")
    p.add_argument("--strategy", default=os.getenv("STRATEGY", "combinacao"), help="Estrategia a executar")
    p.add_argument("--saldo", type=float, default=float(os.getenv("SALDO_INICIAL", "100")), help="Saldo inicial USDT")
    p.add_argument("--quantidade", type=float, default=float(os.getenv("QUANTIDADE", "0.01")), help="Quantidade por trade")
    p.add_argument("--interval", default=os.getenv("INTERVAL", "1m"), help="Intervalo dos candles (1m, 5m, etc)")
    p.add_argument("--testnet", action="store_true", default=os.getenv("USE_TESTNET", "false").lower() == "true", help="Usar testnet")
    p.add_argument("--debug", action="store_true", help="Modo debug")
    p.add_argument("--reset-estado", action="store_true", help="Ignora estado salvo anterior")
    return p.parse_args()


SALVAR_ESTADO_A_CADA = 10


def salvar_relatorio(estrategia, symbol, tempo_execucao_segundos):
    summary = estrategia.get_relatorio()
    config = estrategia.get_configuracao()

    os.makedirs('resultados', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"resultados/relatorio_{estrategia.__class__.__name__}_{timestamp}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("RELATORIO DE SIMULACAO\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Simbolo: {symbol}\n")
        f.write(f"Estrategia: {config['nome']}\n")
        f.write(f"Descricao: {config['descricao']}\n")
        f.write(f"Tempo de execucao: {tempo_execucao_segundos:.1f} segundos\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("-" * 70 + "\n")
        f.write("PARAMETROS DA ESTRATEGIA\n")
        f.write("-" * 70 + "\n")
        for param, valor in config['parametros'].items():
            f.write(f"  {param}: {valor}\n")
        f.write("\n" + "-" * 70 + "\n")
        f.write("RESULTADOS DA SIMULACAO\n")
        f.write("-" * 70 + "\n")
        if summary.get('total_trades', 0) == 0:
            f.write("\nNenhum trade foi executado durante o periodo.\n")
        else:
            f.write(f"Total de trades: {summary['total_trades']}\n")
            f.write(f"  - Compras: {summary['total_compras']}\n")
            f.write(f"  - Vendas: {summary['total_vendas']}\n")
            f.write(f"Total comprado: ${summary['total_comprado_usdt']:.2f}\n")
            f.write(f"Total vendido: ${summary['total_vendido_usdt']:.2f}\n")
            f.write(f"LUCRO/PREJUIZO: ${summary['lucro_usdt']:.2f}\n")
            f.write(f"Taxa de acerto: {summary['taxa_acerto']}%\n")
            f.write(f"Saldo final USDT: ${summary['saldo_final_usdt']:.2f}\n")
            f.write(f"Posicao final: {summary['posicao_final']} {symbol.replace('USDT', '')}\n")
            if summary.get('trades_df') is not None:
                f.write("\n" + "-" * 70 + "\n")
                f.write("DETALHAMENTO DOS TRADES\n")
                f.write("-" * 70 + "\n")
                for _, trade in summary['trades_df'].iterrows():
                    f.write(f"\nTrade: {trade['timestamp']} | {trade['tipo']} @ ${trade['preco']:.2f} | Qtd: {trade['quantidade']}\n")
                    if 'motivo' in trade:
                        f.write(f"  Motivo: {trade['motivo']}\n")
    return filename


async def main():
    args = parse_args()
    setup_logger("TradeSimulado", debug=args.debug)

    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')

    estrategia = criar_estrategia(args.strategy, args.symbol, args.saldo, args.quantidade, args.debug)
    estado_persistente = EstadoPersistente()
    tempo_inicio = datetime.now()

    if not args.reset_estado and estado_persistente.existe():
        log.info("Estado salvo encontrado. Restaurando...")
        estado_persistente.carregar(estrategia)
        log.info("Restaurado: saldo=$%.2f, posicao=%.8f, trades=%d",
                 estrategia.saldo_usdt, estrategia.posicao, len(estrategia.trades))

    async_client = None
    try:
        if api_key and api_secret:
            client = Client(api_key, api_secret, testnet=args.testnet)
            log.info("Cliente %s", "Testnet" if args.testnet else "Mainnet")
        else:
            client = Client()
            log.info("Cliente publico (sem autenticacao)")

        log.info("Iniciando coleta LIVE da Binance para %s...", args.symbol)

        import time
        time.sleep(2)
        ticker = client.get_symbol_ticker(symbol=args.symbol)
        current_price = float(ticker['price'])
        log.info("Preco atual: $%.2f | Saldo: $%.2f USDT", current_price, estrategia.saldo_inicial)

        config = estrategia.get_configuracao()
        log.info("Estrategia: %s", config['nome'])
        if args.debug:
            for param, valor in config['parametros'].items():
                log.debug("  %s: %s", param, valor)

        contador_candles = 0
        contador_trades = 0

        def processar_candle(candle_data):
            nonlocal contador_candles, contador_trades
            try:
                if not candle_data:
                    return
                kline = candle_data['k']
                if not kline['x']:
                    return
                close_price = float(kline['c'])
                high_price = float(kline['h'])
                low_price = float(kline['l'])
                volume = float(kline['v'] if kline['v'] else 0)
                timestamp = datetime.fromtimestamp(kline['T'] / 1000)
                contador_candles += 1
                if contador_candles % 5 == 0:
                    log.info("[%s] C:%.2f H:%.2f L:%.2f V:%.2f",
                             timestamp.strftime('%H:%M:%S'), close_price, high_price, low_price, volume)
                trades = estrategia.processar_preco(
                    preco=close_price, timestamp=timestamp,
                    high=high_price, low=low_price, volume=volume)
                if trades:
                    contador_trades += len(trades)
                    log.info(">>> TRADE EXECUTADO! Total: %d", contador_trades)
                if contador_candles % SALVAR_ESTADO_A_CADA == 0:
                    estado_persistente.salvar(estrategia)
            except Exception as e:
                log.error("Erro ao processar candle: %s", e)

        for tentativa in range(5):
            try:
                if async_client:
                    await async_client.close_connection()
                async_client = await AsyncClient.create(
                    api_key=api_key, api_secret=api_secret, testnet=args.testnet)
                bsm = BinanceSocketManager(async_client)
                log.info("Conectando WebSocket... (tentativa %d/5)", tentativa + 1)
                ts = bsm.kline_socket(symbol=args.symbol, interval=args.interval)
                log.info("WebSocket conectado! Processando candles de %s...", args.interval)
                log.info("Pressione Ctrl+C para parar")
                async with ts as tscm:
                    while True:
                        msg = await tscm.recv()
                        processar_candle(msg)
            except asyncio.CancelledError:
                log.info("Parando coleta...")
                break
            except (ConnectionError, OSError) as e:
                log.warning("Erro de conexao: %s", e)
                if tentativa < 4:
                    await asyncio.sleep(2 * (2 ** tentativa))
                else:
                    log.error("Maximo de tentativas excedido.")
                    raise
    except Exception as e:
        log.error("Erro: %s", e)
        import traceback
        traceback.print_exc()
    finally:
        if async_client:
            await async_client.close_connection()
        estado_persistente.salvar(estrategia)
        tempo_execucao = (datetime.now() - tempo_inicio).total_seconds()
        filename = salvar_relatorio(estrategia, args.symbol, tempo_execucao)
        summary = estrategia.get_relatorio()
        if summary.get('total_trades', 0) > 0:
            log.info("Total trades: %d | Lucro: $%.2f (%s%%) | Portfolio: $%.2f",
                     summary['total_trades'], summary['lucro_usdt'],
                     summary['retorno_percentual'], summary['valor_total_portfolio'])
        else:
            log.info("Nenhum trade executado.")
        log.info("Relatorio salvo em: %s", filename)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[FIM] Programa finalizado pelo usuario")
    except Exception as e:
        log.error("Erro fatal: %s", e)
        import traceback
        traceback.print_exc()
