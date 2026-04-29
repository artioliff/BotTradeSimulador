# estrategias/rsi.py
from .base import EstrategiaBase
from collections import deque

class RSIStrategy(EstrategiaBase):
    """
    Estrategia baseada no Indice de Forca Relativa (RSI).
    
    Compra quando RSI entra em sobrevenda (abaixo do limite inferior).
    Vende quando RSI entra em sobrecompra (acima do limite superior).
    Com protecao de STOP-LOSS (2%), TAKE-PROFIT (3%) e TRAILING STOP (1%).
    """
    
    def __init__(self, symbol, periodo=14, limite_inferior=30, limite_superior=70, 
                 quantidade_por_trade=0.001, percentual_por_trade=None, saldo_inicial=10000, 
                 usar_saida_gradual=False, stop_loss_percent=0.02, take_profit_percent=0.03, 
                 trailing_stop_percent=0.01):
        """
        Args:
            symbol: Simbolo do ativo (ex: BTCUSDT)
            periodo: Periodo para calculo do RSI (padrao: 14)
            limite_inferior: Limite de sobrevenda (padrao: 30)
            limite_superior: Limite de sobrecompra (padrao: 70)
            quantidade_por_trade: Quantidade fixa por operacao
            percentual_por_trade: Percentual do saldo a usar (ex: 0.25 = 25%) - SOBRESCREVE quantidade_por_trade
            saldo_inicial: Saldo inicial em USDT
            usar_saida_gradual: Se True, vende em partes
            stop_loss_percent: Percentual de stop-loss (ex: 0.02 = 2%)
            take_profit_percent: Percentual de take-profit (ex: 0.03 = 3%)
            trailing_stop_percent: Percentual de trailing stop (ex: 0.01 = 1%)
        """
        super().__init__(symbol, saldo_inicial)
        self.periodo = periodo
        self.limite_inferior = limite_inferior
        self.limite_superior = limite_superior
        self.quantidade_por_trade = quantidade_por_trade
        self.percentual_por_trade = percentual_por_trade
        self.usar_saida_gradual = usar_saida_gradual
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        
        self.historico_precos = deque(maxlen=1000)
        self.historico_rsi = deque(maxlen=1000)
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0  # Para trailing stop
        self.niveis_saida = [1.0, 1.02, 1.04, 1.06] if usar_saida_gradual else [1.0]
    
    def processar_preco(self, preco, timestamp):
        """
        Processa cada preco em tempo real.
        Ordem de verificacao:
        1. STOP-LOSS (se perdeu mais que o percentual configurado)
        2. TAKE-PROFIT (se ganhou mais que o percentual configurado)
        3. TRAILING STOP (se caiu do pico)
        4. Sinais normais de RSI (sobrevenda/sobrecompra)
        """
        self.ultimo_preco = preco
        self.historico_precos.append(preco)
        
        # So calcula RSI quando tiver dados suficientes
        if len(self.historico_precos) < self.periodo + 1:
            return []
        
        # Calcula RSI (usando metodo da classe base)
        rsi = self.calcular_rsi_wilder(self.historico_precos, self.periodo)
        self.historico_rsi.append({'timestamp': timestamp, 'rsi': rsi, 'preco': preco})
        
        # Log periodico do RSI
        if len(self.historico_rsi) % 10 == 0:
            print(f"  RSI: {rsi:.1f} | Sobrecompra: {rsi >= self.limite_superior} | Sobrevenda: {rsi <= self.limite_inferior}")
        
        ordens_executadas = []
        
        # ============================================
        # 1. VERIFICACAO DE STOP-LOSS E TAKE-PROFIT (COMBINADOS)
        # ============================================
        if self.em_posicao and self.preco_compra_medio > 0:
            perda_percentual = (preco - self.preco_compra_medio) / self.preco_compra_medio
            lucro_percentual = -perda_percentual
            
            stop_loss_triggered = perda_percentual <= -self.stop_loss_percent
            take_profit_triggered = lucro_percentual >= self.take_profit_percent
            
            if stop_loss_triggered or take_profit_triggered:
                motivo = 'STOP_LOSS' if stop_loss_triggered else 'TAKE_PROFIT'
                percentual = perda_percentual if stop_loss_triggered else lucro_percentual
                
                print(f"  >>> {motivo} ACIONADO! {'Perda' if stop_loss_triggered else 'Lucro'} de {abs(percentual)*100:.1f}%")
                trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp, 
                                           motivo=motivo, rsi=rsi)
                if trade:
                    self.em_posicao = False
                    self.quantidade_comprada_total = 0
                    self.preco_compra_medio = 0
                    self.maior_preco_posicao = 0
                    ordens_executadas.append(trade)
                    return ordens_executadas
        
        # ============================================
        # 2. VERIFICACAO DE TRAILING STOP (STOP MOVEL)
        # ============================================
        if self.em_posicao and self.preco_compra_medio > 0:
            # Atualiza o maior preco desde a compra
            if preco > self.maior_preco_posicao:
                self.maior_preco_posicao = preco
                if len(self.historico_rsi) % 20 == 0:
                    print(f"  Novo pico: ${self.maior_preco_posicao:.2f}")
            
            # Trailing stop: vende se cair X% do pico
            queda_do_pico = (self.maior_preco_posicao - preco) / self.maior_preco_posicao
            if queda_do_pico >= self.trailing_stop_percent and self.maior_preco_posicao > self.preco_compra_medio:
                print(f"  >>> TRAILING STOP ACIONADO! Caiu {queda_do_pico*100:.1f}% do pico de ${self.maior_preco_posicao:.2f}")
                trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp, 
                                           motivo='TRAILING_STOP',
                                           rsi=rsi,
                                           queda_percentual=round(queda_do_pico*100, 2),
                                           pico=self.maior_preco_posicao)
                if trade:
                    self.em_posicao = False
                    self.quantidade_comprada_total = 0
                    self.preco_compra_medio = 0
                    self.maior_preco_posicao = 0
                    ordens_executadas.append(trade)
                    return ordens_executadas
        
        # ============================================
        # 4. SINAIS NORMAIS DE RSI
        # ============================================
        
        # Sinal de compra (RSI em sobrevenda)
        if rsi <= self.limite_inferior and not self.em_posicao:
            # Filtro: só compra se preço está acima da média móvel de 200 períodos
            if len(self.historico_precos) >= 200:
                # Converte deque para lista para poder usar slicing
                precos_lista = list(self.historico_precos)
                media_200 = sum(precos_lista[-200:]) / 200
                if preco < media_200 * 0.98:  # Muito abaixo da média, pode cair mais
                    print(f"  [FILTRO] Preço muito abaixo da média 200, ignorando compra")
                    return ordens_executadas
            
            # Calcula a quantidade baseada no tipo de configuracao
            if self.percentual_por_trade:
                # Usa percentual do saldo atual
                valor_investir = self.saldo_usdt * self.percentual_por_trade
                quantidade = round(valor_investir / preco, 6)
                print(f"  Investindo {self.percentual_por_trade*100}% do saldo (${self.saldo_usdt:.2f}) = ${valor_investir:.2f} -> {quantidade:.6f} BTC")
            else:
                # Usa quantidade fixa
                quantidade = self.quantidade_por_trade
            
            trade = self.executar_compra(preco, quantidade, timestamp, 
                                        rsi=rsi, 
                                        sinal='SOBREVENDA')
            if trade:
                self.em_posicao = True
                self.preco_compra_medio = preco
                self.quantidade_comprada_total = quantidade
                self.maior_preco_posicao = preco
                ordens_executadas.append(trade)
        
        # Sinal de venda (RSI em sobrecompra)
        elif rsi >= self.limite_superior and self.em_posicao:
            quantidade_vender = self.quantidade_comprada_total
            
            # Saida gradual (se configurado)
            if self.usar_saida_gradual and self.preco_compra_medio > 0:
                ganho_percentual = (preco / self.preco_compra_medio) - 1
                if ganho_percentual >= 0.06:
                    quantidade_vender = self.quantidade_comprada_total * 0.25
                elif ganho_percentual >= 0.04:
                    quantidade_vender = self.quantidade_comprada_total * 0.25
                elif ganho_percentual >= 0.02:
                    quantidade_vender = self.quantidade_comprada_total * 0.25
                else:
                    quantidade_vender = self.quantidade_comprada_total
            
            trade = self.executar_venda(preco, quantidade_vender, timestamp, 
                                       rsi=rsi, 
                                       sinal='SOBRECOMPRA')
            if trade:
                self.quantidade_comprada_total -= quantidade_vender
                if self.quantidade_comprada_total <= 0:
                    self.em_posicao = False
                    self.quantidade_comprada_total = 0
                    self.preco_compra_medio = 0
                    self.maior_preco_posicao = 0
                ordens_executadas.append(trade)
        
        return ordens_executadas
    
    def reset(self):
        """Reseta a estrategia para uma nova simulacao"""
        super().reset()
        self.historico_precos = deque(maxlen=1000)
        self.historico_rsi = deque(maxlen=1000)
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
    
    def get_configuracao(self):
        """Retorna a configuracao atual da estrategia"""
        # Define o tipo de gestão de quantidade
        if self.percentual_por_trade:
            gestao_quantidade = f"{self.percentual_por_trade*100}% do saldo"
        else:
            gestao_quantidade = f"{self.quantidade_por_trade} BTC (fixo)"
        
        return {
            'nome': 'RSI - Relative Strength Index',
            'descricao': 'Compra em sobrevenda (RSI < limite_inferior) e vende em sobrecompra (RSI > limite_superior) com protecao de STOP-LOSS (2%), TAKE-PROFIT (3%) e TRAILING STOP (1%)',
            'parametros': {
                'periodo_rsi': self.periodo,
                'limite_inferior_sobrevenda': self.limite_inferior,
                'limite_superior_sobrecompra': self.limite_superior,
                'gestao_de_quantidade': gestao_quantidade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'saida_gradual': self.usar_saida_gradual,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%"
            }
        }