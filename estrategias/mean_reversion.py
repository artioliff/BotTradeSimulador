from .base import EstrategiaBase

class MeanReversionStrategy(EstrategiaBase):
    """
    Estrategia de Reversão à Média.
    Compra quando preço está muito abaixo da média.
    Vende quando preço está muito acima da média.
    """
    
    def __init__(self, symbol, periodo=20, limiar=0.02,
                 quantidade_por_trade=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        self.periodo = periodo
        self.limiar = limiar  # 2% de desvio da média
        self.quantidade_por_trade = quantidade_por_trade
        self.historico_precos = []
        self.em_posicao = False
    
    def processar_preco(self, preco, timestamp):
        self.historico_precos.append(preco)
        
        if len(self.historico_precos) < self.periodo:
            return []
        
        media = sum(self.historico_precos[-self.periodo:]) / self.periodo
        desvio_percentual = (preco - media) / media
        
        ordens = []
        
        # Preço muito abaixo da média? COMPRA (esperando subir)
        if desvio_percentual <= -self.limiar and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        media=round(media, 2),
                                        desvio=round(desvio_percentual*100, 2))
            if trade:
                self.em_posicao = True
                ordens.append(trade)
        
        # Preço muito acima da média? VENDA (esperando cair)
        elif desvio_percentual >= self.limiar and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_por_trade, timestamp,
                                       media=round(media, 2),
                                       desvio=round(desvio_percentual*100, 2))
            if trade:
                self.em_posicao = False
                ordens.append(trade)
        
        # Quando voltar à média, também realiza lucro
        elif abs(desvio_percentual) < 0.005 and self.em_posicao:  # 0.5% da média
            trade = self.executar_venda(preco, self.quantidade_por_trade, timestamp,
                                       motivo='RETORNO_MEDIA',
                                       media=round(media, 2))
            if trade:
                self.em_posicao = False
                ordens.append(trade)
        
        return ordens