import unittest
import math
from datetime import datetime
from collections import deque
from estrategias.base import EstrategiaBase


class EstrategiaTestavel(EstrategiaBase):
    """Estratégia concreta para testar métodos da classe base"""

    def __init__(self):
        super().__init__("TESTE", saldo_inicial=1000, debug=False)

    def get_configuracao(self):
        return {'nome': 'Teste', 'descricao': '', 'parametros': {}}


class TestCalculoRSI(unittest.TestCase):
    def setUp(self):
        self.est = EstrategiaTestavel()

    def test_rsi_padrao_retorna_50_com_poucos_dados(self):
        precos = [100.0] * 5
        rsi = self.est.calcular_rsi_wilder(precos, periodo=14)
        self.assertEqual(rsi, 50.0)

    def test_rsi_100_para_series_subindo(self):
        precos = list(range(100, 200))
        rsi = self.est.calcular_rsi_wilder(precos, periodo=14)
        self.assertGreater(rsi, 99)

    def test_rsi_0_para_series_descendo(self):
        precos = list(range(200, 100, -1))
        rsi = self.est.calcular_rsi_wilder(precos, periodo=14)
        self.assertLess(rsi, 1)

    def test_rsi_100_para_series_constantes(self):
        """Série constante -> perda_media = 0 -> RSI = 100"""
        precos = [100.0] * 30
        rsi = self.est.calcular_rsi_wilder(precos, periodo=14)
        self.assertEqual(rsi, 100.0)

    def test_rsi_com_lista(self):
        rsi = self.est.calcular_rsi_wilder([100] * 20, periodo=14)
        self.assertEqual(rsi, 100.0)

    def test_rsi_com_deque(self):
        rsi = self.est.calcular_rsi_wilder(deque([100] * 20, maxlen=50), periodo=14)
        self.assertEqual(rsi, 100.0)


class TestCalculoEMA(unittest.TestCase):
    def setUp(self):
        self.est = EstrategiaTestavel()

    def test_ema_retorna_none_com_poucos_dados(self):
        self.assertIsNone(self.est.calcular_media_movel_exponencial([100], periodo=14))

    def test_ema_constante(self):
        precos = [100.0] * 30
        ema = self.est.calcular_media_movel_exponencial(precos, periodo=14)
        self.assertIsNotNone(ema)
        self.assertAlmostEqual(ema, 100.0, delta=0.01)

    def test_ema_subindo(self):
        precos = list(range(100, 200))
        ema = self.est.calcular_media_movel_exponencial(precos, periodo=14)
        self.assertGreater(ema, 100)

    def test_ema_com_deque(self):
        ema = self.est.calcular_media_movel_exponencial(deque(range(100, 200), maxlen=200), periodo=14)
        self.assertIsNotNone(ema)
        self.assertGreater(ema, 100)


class TestCalculoSMA(unittest.TestCase):
    def setUp(self):
        self.est = EstrategiaTestavel()

    def test_sma_none_com_poucos_dados(self):
        self.assertIsNone(self.est.calcular_media_movel_simples([100], periodo=14))

    def test_sma_correto(self):
        precos = [10, 20, 30, 40, 50]
        sma = self.est.calcular_media_movel_simples(precos, periodo=3)
        self.assertAlmostEqual(sma, 40.0)

    def test_sma_ultimos_n(self):
        precos = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        sma = self.est.calcular_media_movel_simples(precos, periodo=3)
        self.assertAlmostEqual(sma, (8+9+10)/3)


class TestExecucaoTrades(unittest.TestCase):
    def setUp(self):
        self.est = EstrategiaTestavel()

    def test_compra_reduz_saldo(self):
        self.est.executar_compra(100, 1)
        self.assertAlmostEqual(self.est.saldo_usdt, 900)
        self.assertAlmostEqual(self.est.posicao, 1)
        self.assertTrue(self.est.em_posicao)

    def test_venda_aumenta_saldo(self):
        self.est.executar_compra(100, 5)
        self.est.executar_venda(110, 5)
        self.assertAlmostEqual(self.est.saldo_usdt, 1000 + 50)
        self.assertAlmostEqual(self.est.posicao, 0)
        self.assertFalse(self.est.em_posicao)

    def test_compra_saldo_insuficiente(self):
        trade = self.est.executar_compra(1000000, 1)
        self.assertIsNone(trade)

    def test_venda_sem_posicao(self):
        trade = self.est.executar_venda(100, 1)
        self.assertIsNone(trade)

    def test_venda_parcial(self):
        self.est.executar_compra(100, 5)
        self.est.executar_venda(110, 2)
        self.assertAlmostEqual(self.est.posicao, 3)
        self.assertTrue(self.est.em_posicao)

    def test_trade_registrado(self):
        self.est.executar_compra(100, 1, motivo='teste')
        self.assertEqual(len(self.est.trades), 1)
        self.assertEqual(self.est.trades[0]['tipo'], 'BUY')
        self.assertEqual(self.est.trades[0]['motivo'], 'teste')

    def test_volatilidade(self):
        precos = [100 + math.sin(i * 0.5) * 10 for i in range(50)]
        vol = self.est.calcular_volatilidade(precos, periodo=20)
        self.assertIsNotNone(vol)
        self.assertGreater(vol, 0)

    def test_volatilidade_none_poucos_dados(self):
        self.assertIsNone(self.est.calcular_volatilidade([100, 101], periodo=20))


class TestRelatorio(unittest.TestCase):
    def setUp(self):
        self.est = EstrategiaTestavel()

    def test_relatorio_sem_trades(self):
        rel = self.est.get_relatorio()
        self.assertEqual(rel['total_trades'], 0)

    def test_relatorio_com_trades(self):
        self.est.executar_compra(100, 2)
        self.est.executar_venda(110, 2)
        rel = self.est.get_relatorio()
        self.assertEqual(rel['total_trades'], 2)
        self.assertAlmostEqual(rel['lucro_usdt'], 20.0)
        self.assertAlmostEqual(rel['taxa_acerto'], 100.0)
        self.assertAlmostEqual(rel['retorno_percentual'], 2.0, delta=0.01)

    def test_relatorio_prejuizo(self):
        self.est.executar_compra(100, 2)
        self.est.executar_venda(90, 2)
        rel = self.est.get_relatorio()
        self.assertAlmostEqual(rel['lucro_usdt'], -20.0)
        self.assertAlmostEqual(rel['taxa_acerto'], 0.0)


class TestVerificarStopTakeTrailing(unittest.TestCase):
    def setUp(self):
        self.est = EstrategiaTestavel()
        self.est.maior_preco_posicao = 0
        self.est.executar_compra(100, 1)
        self.est.preco_compra_medio = 100
        self.est.quantidade_comprada_total = 1

    def test_stop_loss_dispara(self):
        trade = self.est._verificar_stop_take_trailing(
            95, datetime.now(), 0.02, 0.03, 0.01)
        self.assertIsNotNone(trade)
        self.assertEqual(trade['motivo'], 'STOP_LOSS')

    def test_take_profit_dispara(self):
        trade = self.est._verificar_stop_take_trailing(
            105, datetime.now(), 0.02, 0.03, 0.01)
        self.assertIsNotNone(trade)
        self.assertEqual(trade['motivo'], 'TAKE_PROFIT')

    def test_nenhum_dispara(self):
        trade = self.est._verificar_stop_take_trailing(
            101, datetime.now(), 0.02, 0.03, 0.01)
        self.assertIsNone(trade)

    def test_sem_posicao_retorna_none(self):
        self.est.em_posicao = False
        trade = self.est._verificar_stop_take_trailing(
            80, datetime.now(), 0.02, 0.03, 0.01)
        self.assertIsNone(trade)


if __name__ == '__main__':
    import math
    unittest.main()
