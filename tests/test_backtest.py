import unittest
from backtest import gerar_dados_sinteticos, gerar_tendencia_com_mudancas
from estrategias.rsi import RSIStrategy


class TestGeracaoDados(unittest.TestCase):
    def test_gerar_dados_sinteticos(self):
        candles = gerar_dados_sinteticos(precos_inicial=100, n_candles=100)
        self.assertEqual(len(candles), 100)
        for c in candles:
            self.assertIn('timestamp', c)
            self.assertIn('open', c)
            self.assertIn('high', c)
            self.assertIn('low', c)
            self.assertIn('close', c)
            self.assertIn('volume', c)
            self.assertGreaterEqual(c['high'], c['low'])
            self.assertGreaterEqual(c['high'], c['close'])
            self.assertGreaterEqual(c['high'], c['open'])
            self.assertLessEqual(c['low'], c['close'])
            self.assertLessEqual(c['low'], c['open'])

    def test_gerar_dados_reprodutiveis(self):
        a = gerar_dados_sinteticos(seed=42, n_candles=50)
        b = gerar_dados_sinteticos(seed=42, n_candles=50)
        for ca, cb in zip(a, b):
            self.assertEqual(ca['close'], cb['close'])

    def test_dados_diferentes_com_seed_diferente(self):
        a = gerar_dados_sinteticos(seed=1, n_candles=50)
        b = gerar_dados_sinteticos(seed=2, n_candles=50)
        self.assertNotEqual(a[-1]['close'], b[-1]['close'])

    def test_tendencia_com_mudancas(self):
        candles = gerar_tendencia_com_mudancas(precos_inicial=100, n_candles=300)
        self.assertEqual(len(candles), 300)
        for c in candles:
            self.assertGreaterEqual(c['high'], c['low'])


class TestBacktestExecucao(unittest.TestCase):
    def test_backtest_com_rsi(self):
        from backtest import executar_backtest
        est = RSIStrategy("TESTE", periodo=14, limite_inferior=30, limite_superior=70,
                          quantidade_por_trade=0.1, saldo_inicial=1000)
        candles = gerar_dados_sinteticos(precos_inicial=100, n_candles=300)
        relatorio = executar_backtest(est, candles, verbose=False)

        self.assertIn('total_trades', relatorio)
        self.assertIn('lucro_usdt', relatorio)
        self.assertIn('taxa_acerto', relatorio)
        self.assertIn('tempo_execucao', relatorio)
        self.assertIn('candles_processados', relatorio)
        self.assertEqual(relatorio['candles_processados'], 300)

    def test_backtest_reseta_estrategia(self):
        from backtest import executar_backtest
        est = RSIStrategy("TESTE", periodo=14, quantidade_por_trade=0.1, saldo_inicial=1000)

        est.historico_precos.append(100)
        est.executar_compra(100, 10)
        self.assertEqual(len(est.trades), 1)

        candles = gerar_dados_sinteticos(n_candles=100)
        executar_backtest(est, candles, verbose=False)

        self.assertNotEqual(len(est.trades), 1)


if __name__ == '__main__':
    from datetime import datetime
    unittest.main()
