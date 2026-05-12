from .base import EstrategiaBase


class MeanReversionStrategy(EstrategiaBase):
    def __init__(self, symbol: str, periodo: int = 20, limiar: float = 0.02,
                 quantidade_por_trade: float = 0.001, saldo_inicial: float = 10000,
                 stop_loss_percent: float = 0.02, take_profit_percent: float = 0.03,
                 trailing_stop_percent: float = 0.01):
        super().__init__(symbol, saldo_inicial)
        self.periodo = periodo
        self.limiar = limiar
        self.quantidade_por_trade = quantidade_por_trade
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.em_posicao: bool = False
        self.preco_compra_medio: float = 0
        self.quantidade_comprada_total: float = 0
        self.maior_preco_posicao: float = 0

    def processar_preco(self, preco: float, timestamp, **kwargs):
        self.historico_precos.append(preco)

        if len(self.historico_precos) < self.periodo:
            return []

        media = sum(self.historico_precos[-self.periodo:]) / self.periodo
        desvio_percentual = (preco - media) / media

        ordens = []

        if self.em_posicao:
            trade = self._verificar_stop_take_trailing(
                preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
                self.trailing_stop_percent, media=round(media, 2))
            if trade:
                return [trade]

        if desvio_percentual <= -self.limiar and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        media=round(media, 2),
                                        desvio=round(desvio_percentual*100, 2))
            if trade:
                self.em_posicao = True
                self.preco_compra_medio = preco
                self.quantidade_comprada_total = self.quantidade_por_trade
                self.maior_preco_posicao = preco
                ordens.append(trade)

        elif desvio_percentual >= self.limiar and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                       media=round(media, 2),
                                       desvio=round(desvio_percentual*100, 2))
            if trade:
                self.em_posicao = False
                self.quantidade_comprada_total = 0
                self.preco_compra_medio = 0
                self.maior_preco_posicao = 0
                ordens.append(trade)

        elif abs(desvio_percentual) < 0.005 and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                       motivo='RETORNO_MEDIA',
                                       media=round(media, 2))
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

    def get_configuracao(self):
        return {
            'nome': 'Reversao a Media',
            'descricao': 'Compra quando preco desvia X% abaixo da media, vende quando desvia X% acima ou retorna a media.',
            'parametros': {
                'periodo_media': self.periodo,
                'limiar_desvio_percentual': f"{self.limiar * 100}%",
                'quantidade_por_trade': self.quantidade_por_trade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%"
            }
        }
