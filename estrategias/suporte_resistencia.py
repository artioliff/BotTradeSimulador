from .base import EstrategiaBase


class SuporteResistenciaStrategy(EstrategiaBase):
    def __init__(self, symbol: str, lookback: int = 100,
                 sensibilidade: float = 0.005,
                 quantidade_por_trade: float = 0.001,
                 saldo_inicial: float = 10000,
                 stop_loss_percent: float = 0.02,
                 take_profit_percent: float = 0.03,
                 trailing_stop_percent: float = 0.01):
        super().__init__(symbol, saldo_inicial)
        self.lookback = lookback
        self.sensibilidade = sensibilidade
        self.quantidade_por_trade = quantidade_por_trade
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.em_posicao: bool = False
        self.preco_compra_medio: float = 0
        self.quantidade_comprada_total: float = 0
        self.maior_preco_posicao: float = 0
        self._niveis_cache: tuple[list[float], list[float]] = ([], [])
        self._cache_tick: int = 0
        self._recalcular_a_cada: int = 10

    def _encontrar_niveis(self, precos):
        if len(precos) < self.lookback:
            return [], []

        precos_analise = precos[-self.lookback:]

        suportes = []
        resistencias = []

        for i in range(2, len(precos_analise) - 2):
            if (precos_analise[i-1] > precos_analise[i] < precos_analise[i+1]):
                suportes.append(precos_analise[i])
            elif (precos_analise[i-1] < precos_analise[i] > precos_analise[i+1]):
                resistencias.append(precos_analise[i])

        return suportes, resistencias

    def _obter_niveis(self):
        self._cache_tick += 1
        if self._cache_tick >= self._recalcular_a_cada:
            self._niveis_cache = self._encontrar_niveis(list(self.historico_precos))
            self._cache_tick = 0
        return self._niveis_cache

    @staticmethod
    def _is_proximo_nivel(preco: float, niveis: list[float], tolerancia: float) -> float | None:
        for nivel in niveis:
            if abs(preco - nivel) / nivel <= tolerancia:
                return nivel
        return None

    def processar_preco(self, preco: float, timestamp, **kwargs):
        self.historico_precos.append(preco)

        if len(self.historico_precos) < self.lookback:
            return []

        if self.em_posicao:
            trade = self._verificar_stop_take_trailing(
                preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
                self.trailing_stop_percent)
            if trade:
                return [trade]

        suportes, resistencias = self._obter_niveis()

        ordens = []

        suporte_proximo = self._is_proximo_nivel(preco, suportes, self.sensibilidade)
        if suporte_proximo is not None and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        nivel='SUPORTE', valor_nivel=round(suporte_proximo, 2))
            if trade:
                self.em_posicao = True
                self.preco_compra_medio = preco
                self.quantidade_comprada_total = self.quantidade_por_trade
                self.maior_preco_posicao = preco
                ordens.append(trade)

        resistencia_proxima = self._is_proximo_nivel(preco, resistencias, self.sensibilidade)
        if resistencia_proxima is not None and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                       nivel='RESISTENCIA', valor_nivel=round(resistencia_proxima, 2))
            if trade:
                self.em_posicao = False
                self.quantidade_comprada_total = 0
                self.preco_compra_medio = 0
                self.maior_preco_posicao = 0
                ordens.append(trade)

        return ordens

    def reset(self):
        super().reset()
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self._niveis_cache = ([], [])
        self._cache_tick = 0

    def get_configuracao(self):
        return {
            'nome': 'Suporte e Resistencia',
            'descricao': 'Compra em niveis de suporte, vende em resistencia. Com stop-loss, take-profit e trailing stop.',
            'parametros': {
                'lookback': self.lookback,
                'sensibilidade_percentual': f"{self.sensibilidade * 100}%",
                'quantidade_por_trade': self.quantidade_por_trade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%"
            }
        }
