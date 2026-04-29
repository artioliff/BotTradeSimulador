from .base import EstrategiaBase

class ADXStrategy(EstrategiaBase):
    """
    Estrategia baseada em ADX para tendências fortes.
    Compra em tendência de alta forte.
    Vende em tendência de baixa forte.
    """
    
    def __init__(self, symbol, periodo=14, limiar_tendencia=25,
                 quantidade_por_trade=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        self.periodo = periodo
        self.limiar_tendencia = limiar_tendencia
        self.quantidade_por_trade = quantidade_por_trade
        self.historico_precos = []
        self.historico_adx = []
        self.em_posicao = False
    
    def calcular_adx(self, highs, lows, closes):
        """Calcula ADX (simplificado)"""
        if len(closes) < self.periodo + 1:
            return None
        
        # TR (True Range)
        tr = []
        for i in range(1, len(closes)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i-1])
            lc = abs(lows[i] - closes[i-1])
            tr.append(max(hl, hc, lc))
        
        # DM+ e DM-
        plus_dm = []
        minus_dm = []
        for i in range(1, len(closes)):
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
        
        # Simplificado: se preço atual > preço anterior -> tendência alta
        tendencia = 'ALTA' if closes[-1] > closes[-2] else 'BAIXA'
        
        # ADX aproximado (simplificado)
        adx = (sum(tr[-self.periodo:]) / self.periodo) > (sum(tr[-self.periodo*2:-self.periodo]) / self.periodo)
        
        return tendencia, adx
    
    def processar_preco(self, preco, timestamp):
        self.historico_precos.append(preco)
        
        # Para simplificar, usamos apenas closes
        if len(self.historico_precos) < self.periodo + 1:
            return []
        
        # Simula highs/lows próximos ao close
        highs = [p * 1.001 for p in self.historico_precos]
        lows = [p * 0.999 for p in self.historico_precos]
        
        tendencia, adx_forte = self.calcular_adx(highs, lows, self.historico_precos)
        
        ordens = []
        
        # Tendência forte de alta
        if tendencia == 'ALTA' and adx_forte and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        tendencia=tendencia, adx='FORTE')
            if trade:
                self.em_posicao = True
                ordens.append(trade)
        
        # Tendência forte de baixa
        elif tendencia == 'BAIXA' and adx_forte and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_por_trade, timestamp,
                                       tendencia=tendencia, adx='FORTE')
            if trade:
                self.em_posicao = False
                ordens.append(trade)
        
        return ordens