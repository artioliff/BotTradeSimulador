import unittest
from datetime import datetime
from estrategias.combinacao import CombinacaoStrategy


class TestCombinacaoStrategy(unittest.TestCase):
    def setUp(self):
        self.est = CombinacaoStrategy(
            symbol="TESTE",
            periodo_rsi=14,
            limite_rsi_inf=30,
            limite_rsi_sup=70,
            quantidade_por_trade=0.1,
            saldo_inicial=1000,
            stop_loss_percent=0.05,
            take_profit_percent=0.10,
            usar_filtro_tendencia=False,
            debug=False
        )
        self.t0 = datetime.now()

    def _alimentar(self, precos: list[float]):
        trades = []
        for p in precos:
            t = self.est.processar_preco(p, self.t0, volume=1000)
            trades.extend(t or [])
        return trades

    def test_sem_sinais_com_poucos_dados(self):
        trades = self.est.processar_preco(100, self.t0, volume=1000)
        self.assertEqual(trades, [])

    def test_acoes_com_dados_suficientes(self):
        precos = [100] * 100
        trades = self._alimentar(precos)
        self.assertIsNotNone(trades)

    def test_get_configuracao(self):
        config = self.est.get_configuracao()
        self.assertIn('nome', config)
        self.assertIn('parametros', config)
        self.assertEqual(config['parametros']['periodo_rsi'], 14)

    def test_reset_limpa_estado(self):
        self.est.preco_compra_medio = 100
        self.est.em_posicao = True
        self.est.quantidade_comprada_total = 0.5
        self.est.reset()
        self.assertEqual(self.est.preco_compra_medio, 0)
        self.assertFalse(self.est.em_posicao)
        self.assertEqual(self.est.quantidade_comprada_total, 0)


class TestIndicadoresCombinacao(unittest.TestCase):
    def setUp(self):
        self.est = CombinacaoStrategy(
            symbol="TESTE",
            periodo_rsi=14,
            limite_rsi_inf=30,
            limite_rsi_sup=70,
            quantidade_por_trade=0.1,
            saldo_inicial=1000,
            debug=False
        )

    def test_ema_correto(self):
        precos = [10, 20, 30, 40, 50]
        ema = self.est._calcular_ema_corrigido(precos, periodo=3)
        self.assertIsNotNone(ema)

    def test_bandas_bollinger(self):
        precos = [100 + i for i in range(30)]
        sup, med, inf, larg = self.est._calcular_bandas(precos)
        self.assertIsNotNone(sup)
        self.assertIsNotNone(med)
        self.assertIsNotNone(inf)
        self.assertGreater(sup, med)
        self.assertLess(inf, med)
        self.assertGreater(larg, 0)

    def test_macd(self):
        precos = [100 + i for i in range(50)]
        self.est.historico_precos.extend(precos)
        macd_line, signal, hist = self.est._calcular_macd_corrigido(self.est.historico_precos)
        self.assertIsNotNone(macd_line)

    def test_tendencia_ema200(self):
        precos = [100] * 250
        self.est.historico_precos.extend(precos)
        tendencia, forca = self.est._calcular_tendencia_ema200()
        self.assertIn(tendencia, ['ALTA', 'BAIXA', 'LATERAL', 'NEUTRO'])

    def test_analise_sinais_retorna_decisao(self):
        comprar, vender, detalhes = self.est._analisar_sinais(
            preco=100, rsi=25, macd_line=1, macd_signal=0.5, histograma=0.5,
            banda_sup=110, media_bb=100, banda_inf=90
        )
        self.assertIsInstance(comprar, bool)
        self.assertIsInstance(vender, bool)
        self.assertIn('count_compra', detalhes)
        self.assertIn('pontuacao_compra', detalhes)


if __name__ == '__main__':
    unittest.main()
