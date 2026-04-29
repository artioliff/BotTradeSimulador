from .base import EstrategiaBase

class SuporteResistenciaStrategy(EstrategiaBase):
    """
    Estrategia baseada em Suporte e Resistência.
    Compra em níveis de suporte, vende em resistência.
    """
    
    def __init__(self, symbol, lookback=100, sensibilidade=0.005,
                 quantidade_por_trade=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        self.lookback = lookback
        self.sensibilidade = sensibilidade  # 0.5% de tolerância
        self.quantidade_por_trade = quantidade_por_trade
        self.historico_precos = []
        self.niveis = {'suporte': [], 'resistencia': []}
        self.em_posicao = False
    
    def encontrar_niveis(self, precos):
        """Encontra niveis de suporte e resistencia"""
        if len(precos) < self.lookback:
            return [], []
        
        precos_analise = precos[-self.lookback:]
        
        suportes = []
        resistencias = []
        
        for i in range(2, len(precos_analise) - 2):
            # Identifica mínimo local (suporte)
            if (precos_analise[i-1] > precos_analise[i] < precos_analise[i+1]):
                suportes.append(precos_analise[i])
            
            # Identifica máximo local (resistência)
            elif (precos_analise[i-1] < precos_analise[i] > precos_analise[i+1]):
                resistencias.append(precos_analise[i])
        
        return suportes, resistencias
    
    def is_proximo_nivel(self, preco, niveis, tolerancia):
        """Verifica se preço está próximo de um nível"""
        for nivel in niveis:
            if abs(preco - nivel) / nivel <= tolerancia:
                return nivel
        return None
    
    def processar_preco(self, preco, timestamp):
        self.historico_precos.append(preco)
        
        if len(self.historico_precos) < self.lookback:
            return []
        
        suportes, resistencias = self.encontrar_niveis(self.historico_precos)
        
        ordens = []
        
        # Próximo ao suporte? COMPRA
        suporte_proximo = self.is_proximo_nivel(preco, suportes, self.sensibilidade)
        if suporte_proximo and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        nivel='SUPORTE', valor_nivel=round(suporte_proximo, 2))
            if trade:
                self.em_posicao = True
                ordens.append(trade)
        
        # Próximo à resistência? VENDA
        resistencia_proxima = self.is_proximo_nivel(preco, resistencias, self.sensibilidade)
        if resistencia_proxima and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_por_trade, timestamp,
                                       nivel='RESISTENCIA', valor_nivel=round(resistencia_proxima, 2))
            if trade:
                self.em_posicao = False
                ordens.append(trade)
        
        return ordens