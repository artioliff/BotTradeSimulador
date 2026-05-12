from .base import EstrategiaBase


class MediaMovelStrategy(EstrategiaBase):
    def __init__(self, symbol: str, periodo_curto: int = 7,
                 periodo_longo: int = 21,
                 quantidade_por_trade: float = 0.01,
                 saldo_inicial: float = 10000):
        super().__init__(symbol, saldo_inicial)
        self.periodo_curto = periodo_curto
        self.periodo_longo = periodo_longo
        self.quantidade_por_trade = quantidade_por_trade
        self.em_posicao: bool = False

    def processar_preco(self, preco: float, timestamp, **kwargs):
        self.ultimo_preco = preco
        self.historico_precos.append(preco)

        if len(self.historico_precos) < self.periodo_longo:
            return []

        media_curta = sum(self.historico_precos[-self.periodo_curto:]) / self.periodo_curto
        media_longa = sum(self.historico_precos[-self.periodo_longo:]) / self.periodo_longo

        ordens_executadas = []

        if media_curta > media_longa and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp)
            if trade:
                self.em_posicao = True
                ordens_executadas.append(trade)

        elif media_curta < media_longa and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_por_trade, timestamp)
            if trade:
                self.em_posicao = False
                ordens_executadas.append(trade)

        return ordens_executadas

    def reset(self):
        super().reset()
        self.em_posicao = False

    def get_configuracao(self):
        return {
            'nome': 'Cruzamento de Medias Moveis',
            'descricao': 'Compra quando media rapida cruza acima da media lenta, vende no cruzamento inverso',
            'parametros': {
                'periodo_curto': self.periodo_curto,
                'periodo_longo': self.periodo_longo,
                'quantidade_por_trade': self.quantidade_por_trade,
                'saldo_inicial_usdt': self.saldo_inicial
            }
        }
