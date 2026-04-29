from .base import EstrategiaBase

class BollingerBandsStrategy(EstrategiaBase):
    """
    Estrategia baseada em Bandas de Bollinger.
    Compra quando preço toca ou cruza banda inferior.
    Vende quando preço toca ou cruza banda superior.
    """
    
    def __init__(self, symbol, periodo=20, desvios=2, 
                 quantidade_por_trade=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        self.periodo = periodo
        self.desvios = desvios
        self.quantidade_por_trade = quantidade_por_trade
        self.historico_precos = []
        self.em_posicao = False
    
    def calcular_bandas(self, precos):
        """Calcula banda superior, media e banda inferior"""
        if len(precos) < self.periodo:
            return None, None, None
        
        preco_atual = precos[-1]
        media = sum(precos[-self.periodo:]) / self.periodo
        
        # Calcula desvio padrão
        variancia = sum((p - media) ** 2 for p in precos[-self.periodo:]) / self.periodo
        desvio = variancia ** 0.5
        
        banda_superior = media + (desvio * self.desvios)
        banda_inferior = media - (desvio * self.desvios)
        
        return banda_superior, media, banda_inferior
    
    def processar_preco(self, preco, timestamp):
        self.historico_precos.append(preco)
        
        if len(self.historico_precos) < self.periodo:
            return []
        
        banda_sup, media, banda_inf = self.calcular_bandas(self.historico_precos)
        
        if banda_sup is None:
            return []
        
        ordens = []
        
        # Compra quando preço toca/ultrapassa banda inferior
        if preco <= banda_inf and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        banda_superior=round(banda_sup, 2),
                                        media=round(media, 2),
                                        banda_inferior=round(banda_inf, 2))
            if trade:
                self.em_posicao = True
                ordens.append(trade)
        
        # Venda quando preço toca/ultrapassa banda superior
        elif preco >= banda_sup and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_por_trade, timestamp,
                                       banda_superior=round(banda_sup, 2),
                                       media=round(media, 2),
                                       banda_inferior=round(banda_inf, 2))
            if trade:
                self.em_posicao = False
                ordens.append(trade)
        
        return ordens