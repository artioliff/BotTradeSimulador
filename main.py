# main.py
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from binance import Client, AsyncClient, BinanceSocketManager

# ============================================
# CONFIGURACOES
# ============================================
load_dotenv()

API_KEY    = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
USE_TESTNET = os.getenv('USE_TESTNET', 'false').lower() == 'true'
SYMBOL = 'BTCUSDT'

# ============================================
# SELECAO DA ESTRATEGIA
# ============================================

# 1. RSI Simples
from estrategias import RSIStrategy

estrategia = RSIStrategy(
    symbol='SOLUSDT', # BTCUSDT
    periodo=14,
    limite_inferior=30,
    limite_superior=70,
    quantidade_por_trade=0.00010,
    saldo_inicial=20,
    stop_loss_percent=0.015,
    take_profit_percent=0.025,
    trailing_stop_percent=0.008,
)

# 2. Grid Spot
# from estrategias import GridSpotStrategy
# estrategia = GridSpotStrategy(
#     symbol='BTCUSDT', num_grids=6, spacing_percent=0.005,
#     quantidade_por_ordem=0.0001, saldo_inicial=20
# )

# 3. Media Movel
# from estrategias import MediaMovelStrategy
# estrategia = MediaMovelStrategy(
#     symbol='BTCUSDT', periodo_curto=7, periodo_longo=21,
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 4. MACD
# from estrategias import MACDStrategy
# estrategia = MACDStrategy(
#     symbol='BTCUSDT', fast_period=12, slow_period=26, signal_period=9,
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 5. Bollinger Bands
# from estrategias import BollingerBandsStrategy
# estrategia = BollingerBandsStrategy(
#     symbol='BTCUSDT', periodo=20, desvios=2,
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 6. Suporte e Resistencia
# from estrategias import SuporteResistenciaStrategy
# estrategia = SuporteResistenciaStrategy(
#     symbol='BTCUSDT', lookback=100, sensibilidade=0.005,
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 7. Mean Reversion
# from estrategias import MeanReversionStrategy
# estrategia = MeanReversionStrategy(
#     symbol='BTCUSDT', periodo=20, limiar=0.02,
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 8. ADX
# from estrategias import ADXStrategy
# estrategia = ADXStrategy(
#     symbol='BTCUSDT', periodo=14, limiar_tendencia=25,
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 9. Multi Timeframe
# from estrategias import MultiTimeframeStrategy
# estrategia = MultiTimeframeStrategy(
#     symbol='BTCUSDT', periodos=[5, 15, 60],
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 10. Scalping
# from estrategias import ScalpingStrategy
# estrategia = ScalpingStrategy(
#     symbol='BTCUSDT', lookback=10, min_variacao=0.001,
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 11. Combinacao RSI + MACD + Bollinger
# from estrategias import CombinacaoStrategy
# estrategia = CombinacaoStrategy(
#     symbol='BTCUSDT', periodo_rsi=14, limite_rsi_inf=30, limite_rsi_sup=70,
#     macd_fast=12, macd_slow=26, macd_signal=9, bb_periodo=20, bb_desvios=2,
#     quantidade_por_trade=0.001, saldo_inicial=10000
# )

# 12. RSI Avancado
# from estrategias import RSIAvancadoStrategy
# estrategia = RSIAvancadoStrategy(
#     symbol='BTCUSDT', periodo=14, limite_inferior=30, limite_superior=70,
#     quantidade_por_trade=0.001, saldo_inicial=10000,
#     usar_divergencia=True, usar_filtro_tendencia=True, periodo_tendencia=200
# )


# ============================================
# FUNCOES AUXILIARES
# ============================================

def salvar_relatorio(estrategia, tempo_execucao_segundos):
    """Salva o relatorio da simulacao em arquivo TXT."""
    summary = estrategia.get_relatorio()
    config = estrategia.get_configuracao()

    os.makedirs('resultados', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"resultados/relatorio_{estrategia.__class__.__name__}_{timestamp}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("RELATORIO DE SIMULACAO\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Simbolo: {SYMBOL}\n")
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
            f.write(f"Total comprado: ${summary['total_comprado_usdt']}\n")
            f.write(f"Total vendido: ${summary['total_vendido_usdt']}\n")
            f.write(f"LUCRO/PREJUIZO: ${summary['lucro_usdt']}\n")
            f.write(f"Taxa de acerto: {summary['taxa_acerto']}%\n")
            f.write(f"Saldo final USDT: ${summary['saldo_final_usdt']}\n")
            f.write(f"Posicao final: {summary['posicao_final']} BTC\n")

            if summary.get('trades_df') is not None:
                f.write("\n" + "-" * 70 + "\n")
                f.write("DETALHAMENTO DOS TRADES\n")
                f.write("-" * 70 + "\n")
                df = summary['trades_df']
                for idx, trade in df.iterrows():
                    f.write(f"\nTrade #{idx + 1}:\n")
                    f.write(f"  Data: {trade['timestamp']}\n")
                    f.write(f"  Tipo: {trade['tipo']}\n")
                    f.write(f"  Preco: ${trade['preco']:.2f}\n")
                    f.write(f"  Quantidade: {trade['quantidade']}\n")
                    if 'rsi' in trade:
                        f.write(f"  RSI no momento: {trade['rsi']:.1f}\n")
                    if 'motivo' in trade:
                        f.write(f"  Motivo: {trade['motivo']}\n")

    return filename


# ============================================
# LOOP PRINCIPAL
# ============================================

async def main():
    async_client = None
    tempo_inicio = datetime.now()

    try:
        # Cria cliente
        if API_KEY and API_SECRET:
            client = Client(API_KEY, API_SECRET, testnet=USE_TESTNET)
            print("✅ Cliente Testnet (API simulada)" if USE_TESTNET else "✅ Cliente Mainnet (API real)")
        else:
            client = Client()
            print("⚠️ Cliente publico (sem autenticacao)")

        print(f"\n🚀 Iniciando coleta LIVE da Binance para {SYMBOL}...")
        print("=" * 70)

        # Preço atual
        ticker = client.get_symbol_ticker(symbol=SYMBOL)
        current_price = float(ticker['price'])
        print(f"💰 Preco atual: ${current_price:.2f}")
        print(f"💵 Saldo inicial: ${estrategia.saldo_inicial:.2f} USDT")

        # Configuração da estratégia
        config = estrategia.get_configuracao()
        print(f"\n📊 Estrategia: {config['nome']}")
        print(f"📈 Descricao: {config['descricao']}")
        print("⚙️ Parametros:")
        for param, valor in config['parametros'].items():
            print(f"    {param}: {valor}")

        # WebSocket
        async_client = await AsyncClient.create(
            api_key=API_KEY,
            api_secret=API_SECRET,
            testnet=USE_TESTNET,
        )
        bsm = BinanceSocketManager(async_client)

        print("\n🔌 Conectando WebSocket...")

        ultimo_preco = None
        contador = 0

        def processar_mensagem(msg):
            nonlocal ultimo_preco, contador
            try:
                if msg and 'k' in msg:
                    preco = float(msg['k']['c'])
                    timestamp = datetime.fromtimestamp(msg['E'] / 1000)

                    # Evita processar o mesmo preço repetido
                    if preco == ultimo_preco:
                        return
                    ultimo_preco = preco
                    contador += 1

                    if contador % 10 == 0:
                        print(f"[{timestamp.strftime('%H:%M:%S')}] 📊 Preço: ${preco:.2f} | Processando...")

                    # Chama o método correto da estratégia
                    estrategia.processar_preco(preco, timestamp)

            except Exception as e:
                print(f"❌ Erro ao processar mensagem: {e}")

        # Inicia socket de klines (candles de 1 minuto)
        ts = bsm.kline_socket(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1MINUTE)

        print("\n✅ WebSocket conectado! Coletando dados em tempo real...")
        print("🛑 Pressione Ctrl+C para parar e salvar o relatório.\n")

        try:
            async with ts as tscm:
                while True:
                    msg = await tscm.recv()
                    processar_mensagem(msg)

        except (asyncio.CancelledError, KeyboardInterrupt):
            print("\n⏹️ Parando coleta...")

    except Exception as e:
        print(f"❌ Erro na conexao: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if async_client:
            try:
                await async_client.close_connection()
            except Exception:
                pass

        tempo_execucao = (datetime.now() - tempo_inicio).total_seconds()
        filename = salvar_relatorio(estrategia, tempo_execucao)

        print("\n" + "=" * 70)
        print("📊 RESUMO DA SIMULACAO")
        print("=" * 70)
        summary = estrategia.get_relatorio()
        if summary.get('total_trades', 0) > 0:
            print(f"📈 Total de trades: {summary['total_trades']}")
            print(f"💰 Lucro/Prejuizo: ${summary['lucro_usdt']}")
            print(f"💵 Saldo final: ${summary['saldo_final_usdt']}")
        else:
            print("⚠️ Nenhum trade foi executado.")

        print(f"\n📄 Relatorio salvo em: {filename}")


def run():
    asyncio.run(main())


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n👋 Programa finalizado pelo usuario")
    except Exception as e:
        print(f"❌ Erro: {e}")