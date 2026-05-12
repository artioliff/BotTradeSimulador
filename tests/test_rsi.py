import unittest
from datetime import datetime
from estrategias.rsi import RSIStrategy


class TestRSIStrategySinais(unittest.TestCase):
    def setUp(self):
        self.est = RSIStrategy(
            symbol="TESTE", periodo=14, limite_inferior=30, limite_superior=70,
            quantidade_por_trade=0.1, saldo_inicial=1000,
            stop_loss_percent=0.05, take_profit_percent=0.10,
            usar_filtro_tendencia=False, usar_filtro_volume=False
        )
        self.t0 = datetime.now()

    def _alimentar_precos(self, precos: list[float]) -> list:
        trades = []
        for i, p in enumerate(precos):
            t = self.est.processar_preco(p, self.t0, volume=1000)
            trades.extend(t or [])
        return trades

    def test_sem_sinais_com_poucos_dados(self):
        trades = self.est.processar_preco(100, self.t0)
        self.assertEqual(trades, [])

    def test_sinal_compra_em_sobrevenda(self):
        precos = [100 + i for i in range(15)]  # sobe
        precos += [100 + i for i in range(15, 0, -1)]  # desce
        precos += [50 + i * 0.5 for i in range(20)]  # continua descendo devagar
        trades = self._alimentar_precos(precos)
        self.assertGreater(len(trades), 0, "Deveria ter gerado ao menos 1 trade")

    def test_sinal_venda_em_sobrecompra(self):
        self.est.em_posicao = True
        self.est.quantidade_comprada_total = 0.1
        self.est.preco_compra_medio = 100
        self.est.maior_preco_posicao = 100

        precos = [100 for _ in range(15)]  # neutro
        precos += [200 - i * 0.5 for i in range(20)]  # cai de 200
        self._alimentar_precos(precos)

        precos_finais = [100]
        for p in precos_finais:
            self.est.processar_preco(p, self.t0, volume=1000)

    def test_filtro_preco_acima_media_200(self):
        self.est.historico_precos.extend([100] * 200)
        self.est.historico_precos.extend([200] * 50)
        self.est.historico_rsi.extend([{'rsi': 40}] * 250)
        comprar = self.est._checar_filtros(200, 25)
        self.assertFalse(comprar)


class TestRSIStrategyReset(unittest.TestCase):
    def test_reset_limpa_estado(self):
        est = RSIStrategy("TESTE", quantidade_por_trade=0.1, saldo_inicial=1000)
        est.executar_compra(100, 0.1, datetime.now())
        self.assertEqual(len(est.trades), 1)
        est.reset()
        self.assertEqual(len(est.trades), 0)
        self.assertAlmostEqual(est.saldo_usdt, 1000)
        self.assertAlmostEqual(est.posicao, 0)
        self.assertFalse(est.em_posicao)


class TestRSIStrategyConfig(unittest.TestCase):
    def test_get_configuracao_retorna_parametros(self):
        est = RSIStrategy("BNBUSDT", periodo=14, limite_inferior=30, limite_superior=70)
        config = est.get_configuracao()
        self.assertEqual(config['nome'], 'RSI - Relative Strength Index (Versão Melhorada)')
        self.assertEqual(config['parametros']['periodo_rsi'], 14)
        self.assertEqual(config['parametros']['limite_inferior_sobrevenda'], 30)
        self.assertEqual(config['parametros']['limite_superior_sobrecompra'], 70)


if __name__ == '__main__':
    unittest.main()
