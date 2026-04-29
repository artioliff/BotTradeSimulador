from .base import EstrategiaBase

class ScalpingStrategy(EstrategiaBase):
    """
    Estrategia de Scalping para movimentos rápidos.
    Opera em pequenas variações de preço.
    """
    
    def __init__(self, symbol, lookback=10, min_variacao=0.001,
                 quantidade_por_trade=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        self.lookback = lookback
        self.min_variacao = min_variacao  # 0.1%
        self.quantidade_por_trade = quantidade_por_trade
        self.historico_precos = []
        self.ultimas_variacoes = []
        self.em_posicao = False
    
    def processar_preco(self, preco, timestamp):
        self.historico_precos.append(preco)
        
        if len(self.historico_precos) < self.lookback + 1:
            return []
        
        # Calcula variação recente
        variacao = (preco - self.historico_precos[-2]) / self.historico_precos[-2]
        self.ultimas_variacoes.append(variacao)
        
        # Média das últimas variações
        if len(self.ultimas_variacoes) > self.lookback:
            self.ultimas_variacoes.pop(0)
        
        media_variacao = sum(self.ultimas_variacoes) / len(self.ultimas_variacoes)
        
        ordens = []
        
        # Momentum positivo forte
        if variacao > self.min_variacao * 2 and media_variacao > 0 and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        variacao=round(variacao*100, 2),
                                        momentum='POSITIVO')
            if trade:
                self.em_posicao = True
                ordens.append(trade)
        
        # Já ganhou um pouco? Realiza lucro rápido
        elif self.em_posicao and self.preco_compra_medio > 0:
            lucro_percentual = (preco - self.preco_compra_medio) / self.preco_compra_medio
            
            # Take-profit rápido (0.3%) ou stop-loss apertado (0.15%)
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