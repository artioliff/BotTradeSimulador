from .base import EstrategiaBase


class MultiTimeframeStrategy(EstrategiaBase):
    def __init__(self, symbol: str, periodos: list[int] | None = None,
                 quantidade_por_trade: float = 0.001,
                 saldo_inicial: float = 10000,
                 stop_loss_percent: float = 0.02,
                 take_profit_percent: float = 0.03,
                 trailing_stop_percent: float = 0.01):
        self.periodos = periodos or [5, 15, 60]
        super().__init__(symbol, saldo_inicial)
        self.quantidade_por_trade = quantidade_por_trade
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.historicos: dict[int, list[float]] = {p: [] for p in self.periodos}
        self.sinais: dict[int, str | None] = {p: None for p in self.periodos}
        self.em_posicao: bool = False
        self.preco_compra_medio: float = 0
        self.quantidade_comprada_total: float = 0
        self.maior_preco_posicao: float = 0

    def calcular_sinal_por_periodo(self, precos: list[float], periodo: int) -> str | None:
        if len(precos) < periodo + 5:
            return None

        media_curta = sum(precos[-periodo:]) / periodo
        media_longa = sum(precos[-periodo*2:]) / (periodo*2)

        if media_curta > media_longa:
            return 'COMPRA'
        elif media_curta < media_longa:
            return 'VENDA'
        return 'NEUTRO'

    def processar_preco(self, preco: float, timestamp, **kwargs):
        for periodo in self.periodos:
            self.historicos[periodo].append(preco)
            if len(self.historicos[periodo]) > periodo * 5:
                self.historicos[periodo] = self.historicos[periodo][-periodo*5:]
            self.sinais[periodo] = self.calcular_sinal_por_periodo(
                self.historicos[periodo], periodo
            )

        if self.em_posicao:
            trade = self._verificar_stop_take_trailing(
                preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
                self.trailing_stop_percent)
            if trade:
                return [trade]

        ordens = []

        compras = sum(1 for s in self.sinais.values() if s == 'COMPRA')
        vendas = sum(1 for s in self.sinais.values() if s == 'VENDA')

        if compras > vendas and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        compras=compras, vendas=vendas,
                                        periodos=self.sinais.copy())
            if trade:
                self.em_posicao = True
                self.preco_compra_medio = preco
                self.quantidade_comprada_total = self.quantidade_por_trade
                self.maior_preco_posicao = preco
                ordens.append(trade)

        elif vendas > compras and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                       compras=compras, vendas=vendas,
                                       periodos=self.sinais.copy())
            if trade:
                self.em_posicao = False
                self.quantidade_comprada_total = 0
                self.preco_compra_medio = 0
                self.maior_preco_posicao = 0
                ordens.append(trade)

        return ordens

    def reset(self):
        super().reset()
        self.historicos = {p: [] for p in self.periodos}
        self.sinais = {p: None for p in self.periodos}
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0

    def get_configuracao(self):
        return {
            'nome': 'Multi-Timeframe',
            'descricao': 'Combina sinais de multiplos periodos com SMA. Decisao por maioria. Com stop-loss, take-profit e trailing stop.',
            'parametros': {
                'periodos': self.periodos,
                'quantidade_por_trade': self.quantidade_por_trade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%"
            }
        }
