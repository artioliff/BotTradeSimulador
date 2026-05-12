from .base import EstrategiaBase


class ScalpingStrategy(EstrategiaBase):
    def __init__(self, symbol: str, lookback: int = 10,
                 min_variacao: float = 0.001,
                 quantidade_por_trade: float = 0.001,
                 saldo_inicial: float = 10000):
        super().__init__(symbol, saldo_inicial)
        self.lookback = lookback
        self.min_variacao = min_variacao
        self.quantidade_por_trade = quantidade_por_trade
        self.ultimas_variacoes: list[float] = []
        self.em_posicao: bool = False
        self.quantidade_comprada_total: float = 0
        self.preco_compra_medio: float = 0

    def processar_preco(self, preco: float, timestamp, **kwargs):
        self.historico_precos.append(preco)

        if len(self.historico_precos) < self.lookback + 1:
            return []

        variacao = (preco - self.historico_precos[-2]) / self.historico_precos[-2]
        self.ultimas_variacoes.append(variacao)

        if len(self.ultimas_variacoes) > self.lookback:
            self.ultimas_variacoes.pop(0)

        media_variacao = sum(self.ultimas_variacoes) / len(self.ultimas_variacoes)

        ordens = []

        if variacao > self.min_variacao * 2 and media_variacao > 0 and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        variacao=round(variacao*100, 2),
                                        momentum='POSITIVO')
            if trade:
                self.em_posicao = True
                self.preco_compra_medio = preco
                self.quantidade_comprada_total = self.quantidade_por_trade
                ordens.append(trade)

        elif self.em_posicao and self.preco_compra_medio > 0:
            lucro_percentual = (preco - self.preco_compra_medio) / self.preco_compra_medio

            if lucro_percentual >= 0.003:
                trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                            motivo='TAKE_PROFIT_SCALP',
                                            lucro=round(lucro_percentual*100, 2))
                if trade:
                    self.em_posicao = False
                    self.quantidade_comprada_total = 0
                    ordens.append(trade)

            elif lucro_percentual <= -0.0015:
                trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                            motivo='STOP_LOSS_SCALP',
                                            perda=round(lucro_percentual*100, 2))
                if trade:
                    self.em_posicao = False
                    self.quantidade_comprada_total = 0
                    ordens.append(trade)

        return ordens

    def reset(self):
        super().reset()
        self.ultimas_variacoes = []
        self.em_posicao = False
        self.quantidade_comprada_total = 0
        self.preco_compra_medio = 0

    def get_configuracao(self):
        return {
            'nome': 'Scalping',
            'descricao': 'Opera movimentos rápidos com take-profit de 0.3% e stop-loss de 0.15%.',
            'parametros': {
                'lookback': self.lookback,
                'variacao_minima_percentual': f"{self.min_variacao * 100}%",
                'quantidade_por_trade': self.quantidade_por_trade,
                'saldo_inicial_usdt': self.saldo_inicial
            }
        }
