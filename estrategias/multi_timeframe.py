from .base import EstrategiaBase

class MultiTimeframeStrategy(EstrategiaBase):
    """
    Estrategia que combina sinais de diferentes períodos.
    Mais confiável por confirmar tendências múltiplas.
    """
    
    def __init__(self, symbol, periodos=[5, 15, 60],
                 quantidade_por_trade=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        self.periodos = periodos
        self.quantidade_por_trade = quantidade_por_trade
        self.historicos = {p: [] for p in periodos}
        self.sinais = {p: None for p in periodos}
        self.em_posicao = False
    
    def calcular_sinal_por_periodo(self, precos, periodo):
        """Calcula sinal baseado em média móvel simples"""
        if len(precos) < periodo + 5:
            return None
        
        media_curta = sum(precos[-periodo:]) / periodo
        media_longa = sum(precos[-periodo*2:]) / (periodo*2)
        
        if media_curta > media_longa:
            return 'COMPRA'
        elif media_curta < media_longa:
            return 'VENDA'
        return 'NEUTRO'
    
    def processar_preco(self, preco, timestamp):
        # Atualiza históricos para cada timeframe
        for periodo in self.periodos:
            self.historicos[periodo].append(preco)
            
            # Mantém tamanho do histórico
            if len(self.historicos[periodo]) > periodo * 5:
                self.historicos[periodo] = self.historicos[periodo][-periodo*5:]
            
            # Calcula sinal
            self.sinais[periodo] = self.calcular_sinal_por_periodo(
                self.historicos[periodo], periodo
            )
        
        ordens = []
        
        # Vota os sinais
        compras = sum(1 for s in self.sinais.values() if s == 'COMPRA')
        vendas = sum(1 for s in self.sinais.values() if s == 'VENDA')
        
        # Decisão por maioria
        if compras > vendas and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        compras=compras, vendas=vendas,
                                        periodos=self.sinais.copy())
            if trade:
                self.em_posicao = True
                ordens.append(trade)
        
        elif vendas > compras and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_por_trade, timestamp,
                                       compras=compras, vendas=vendas,
                                       periodos=self.sinais.copy())
            if trade:
                self.em_posicao = False
                ordens.append(trade)
        
        return ordens