# estrategias/combinacao.py
from .base import EstrategiaBase
from collections import deque
from datetime import datetime

class CombinacaoStrategy(EstrategiaBase):
    """
    Estrategia que combina RSI, MACD e Bollinger Bands (Versão Corrigida).
    
    Características:
    - Votação entre 3 indicadores (precisa de 2+ para operar)
    - Peso diferente para cada indicador (MACD tem mais peso em tendência)
    - Stop-loss, take-profit, trailing stop
    - Filtro de tendência por EMA 200
    - Saída gradual com base na força do sinal
    - Cooldown após perdas consecutivas
    - Confirmação de candle para evitar whipsaw
    """
    
    def __init__(self, symbol, 
                 # RSI params
                 periodo_rsi=14, limite_rsi_inf=30, limite_rsi_sup=70,
                 # MACD params
                 macd_fast=12, macd_slow=26, macd_signal=9,
                 # Bollinger params
                 bb_periodo=20, bb_desvios=2,
                 # Gestão
                 quantidade_por_trade=0.001, percentual_por_trade=None, saldo_inicial=10000,
                 # Pesos dos indicadores
                 peso_rsi=1, peso_macd=1.5, peso_bb=1,
                 # Filtros
                 usar_filtro_tendencia=True, usar_confirmacao_candle=True,
                 # Proteções
                 stop_loss_percent=0.02, take_profit_percent=0.03, trailing_stop_percent=0.01,
                 usar_saida_gradual=False, min_concordancia=2,
                 # Cooldown
                 max_perdas_consecutivas=3, cooldown_periods=10,
                 # Debug
                 debug=False):
        """
        Args:
            symbol: Simbolo do ativo
            periodo_rsi: Periodo do RSI
            limite_rsi_inf: Sobrevenda RSI
            limite_rsi_sup: Sobrecompra RSI
            macd_fast, macd_slow, macd_signal: Parâmetros MACD
            bb_periodo, bb_desvios: Parâmetros Bollinger
            quantidade_por_trade: Quantidade fixa
            percentual_por_trade: Percentual do saldo
            saldo_inicial: Saldo inicial
            peso_rsi, peso_macd, peso_bb: Pesos para cada indicador
            usar_filtro_tendencia: Se True, opera apenas na direção da tendência
            usar_confirmacao_candle: Se True, espera fechamento do candle
            stop_loss_percent, take_profit_percent, trailing_stop_percent: Proteções
            usar_saida_gradual: Se True, vende em partes
            min_concordancia: Mínimo de indicadores concordando (2 ou 3)
            max_perdas_consecutivas: Perdas seguidas antes de pausar
            cooldown_periods: Candles de pausa
            debug: Logs detalhados
        """
        super().__init__(symbol, saldo_inicial, debug=debug)
        
        # RSI
        self.periodo_rsi = periodo_rsi
        self.limite_rsi_inf = limite_rsi_inf
        self.limite_rsi_sup = limite_rsi_sup
        
        # MACD
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal_period = macd_signal
        
        # Bollinger
        self.bb_periodo = bb_periodo
        self.bb_desvios = bb_desvios
        
        # Gestão
        self.quantidade_por_trade = quantidade_por_trade
        self.percentual_por_trade = percentual_por_trade
        
        # Pesos (MACD tem +peso em tendências fortes)
        self.peso_rsi = peso_rsi
        self.peso_macd = peso_macd
        self.peso_bb = peso_bb
        
        # Filtros
        self.usar_filtro_tendencia = usar_filtro_tendencia
        self.usar_confirmacao_candle = usar_confirmacao_candle
        self.min_concordancia = min_concordancia
        
        # Proteções
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.usar_saida_gradual = usar_saida_gradual
        
        # Cooldown
        self.max_perdas_consecutivas = max_perdas_consecutivas
        self.cooldown_periods_counter = 0
        self.cooldown_max_periods = cooldown_periods
        
        # Históricos
        self.historico_macd = deque(maxlen=500)
        self.historico_rsi = deque(maxlen=500)
        self.historico_volumes = deque(maxlen=1000)
        
        # Estado
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self.perdas_consecutivas = 0
        self.volume_atual = 0
        
        # Confirmação
        self.sinal_compra_pendente = False
        self.sinal_venda_pendente = False
        self.preco_sinal_compra = 0
        self.preco_sinal_venda = 0
        
        # Cache EMA200 incremental
        self._ema200: float = 0
        self._ema200_pronta: bool = False

        # Estatísticas
        self.total_sinais_compra = 0
        self.total_sinais_venda = 0
        self.confianca_media_compra = 0
        self.confianca_media_venda = 0
    
    # ============================================
    # CÁLCULOS DOS INDICADORES (CORRIGIDOS)
    # ============================================
    
    def _calcular_ema_corrigido(self, precos, periodo):
        """Calcula EMA corretamente (média simples dos primeiros 'periodo' valores)"""
        if len(precos) < periodo:
            return precos[-1] if precos else 0
        
        # Primeiro valor: média simples dos primeiros 'periodo' preços
        ema = sum(precos[:periodo]) / periodo
        
        # Wilder smoothing
        multiplicador = 2 / (periodo + 1)
        
        for preco in precos[periodo:]:
            ema = (preco - ema) * multiplicador + ema
        
        return ema
    
    def _calcular_macd_corrigido(self, precos):
        """Calcula MACD corretamente com EMAs apropriadas"""
        if len(precos) < self.macd_slow + self.macd_signal_period:
            return 0, 0, 0
        
        # Converte para lista
        precos_lista = list(precos)
        
        # Calcula EMAs
        ema_fast = self._calcular_ema_corrigido(precos_lista, self.macd_fast)
        ema_slow = self._calcular_ema_corrigido(precos_lista, self.macd_slow)
        
        macd_line = ema_fast - ema_slow
        
        # Calcula signal line (EMA do MACD)
        if len(self.historico_macd) >= self.macd_signal_period - 1:
            macd_list = list(self.historico_macd)
            macd_values = [m[0] for m in macd_list[-(self.macd_signal_period - 1):]]
            macd_values.append(macd_line)
            signal_line = self._calcular_ema_corrigido(macd_values, self.macd_signal_period)
        else:
            signal_line = macd_line
        
        # Calcula histograma
        histograma = macd_line - signal_line
        
        return macd_line, signal_line, histograma
    
    def _calcular_rsi(self, precos):
        """Calcula RSI usando método da classe base"""
        return self.calcular_rsi_wilder(precos, self.periodo_rsi)
    
    def _calcular_bandas(self, precos):
        """Calcula bandas de Bollinger"""
        if len(precos) < self.bb_periodo:
            return None, None, None
        
        precos_lista = list(precos)
        ultimos_precos = precos_lista[-self.bb_periodo:]
        
        media = sum(ultimos_precos) / self.bb_periodo
        variancia = sum((p - media) ** 2 for p in ultimos_precos) / self.bb_periodo
        desvio = variancia ** 0.5
        
        banda_superior = media + (desvio * self.bb_desvios)
        banda_inferior = media - (desvio * self.bb_desvios)
        largura = (banda_superior - banda_inferior) / media if media > 0 else 0
        
        return banda_superior, media, banda_inferior, largura
    
    # ============================================
    # FILTRO DE TENDÊNCIA
    # ============================================
    
    def _calcular_tendencia_ema200(self):
        """Calcula tendência baseada em EMA 200 (incremental)"""
        n = len(self.historico_precos)
        if n < 200:
            return 'NEUTRO', 0

        preco_atual = self.historico_precos[-1]

        if not self._ema200_pronta:
            precos_lista = list(self.historico_precos)
            self._ema200 = self._calcular_ema_corrigido(precos_lista, 200)
            self._ema200_pronta = True
        else:
            k = 2 / 201
            self._ema200 = (preco_atual * k) + (self._ema200 * (1 - k))

        ema200 = self._ema200

        if preco_atual > ema200 * 1.03:
            forca = (preco_atual - ema200) / ema200 * 100
            return 'ALTA', forca
        elif preco_atual < ema200 * 0.97:
            forca = (ema200 - preco_atual) / ema200 * 100
            return 'BAIXA', forca
        else:
            return 'LATERAL', 0
    
    # ============================================
    # PROTEÇÕES
    # ============================================
    
    def _calcular_quantidade(self, preco: float):
        if self.percentual_por_trade:
            valor_investir = self.saldo_usdt * self.percentual_por_trade
            quantidade = round(valor_investir / preco, 8)
            return quantidade, valor_investir
        else:
            quantidade = self.quantidade_por_trade
            valor_necessario = quantidade * preco
            
            if valor_necessario > self.saldo_usdt:
                self._log(f"Saldo insuficiente! Necessário ${valor_necessario:.2f}, tem ${self.saldo_usdt:.2f}", "ERRO")
                return None, None
            
            return quantidade, valor_necessario
    
    # ============================================
    # ANÁLISE DE SINAIS
    # ============================================
    
    def _analisar_sinais(self, preco, rsi, macd_line, macd_signal, histograma, 
                         banda_sup, media_bb, banda_inf):
        """
        Analisa sinais dos 3 indicadores com pesos
        Retorna: (sinal_total_compra, sinal_total_venda, detalhes)
        """
        # Sinal RSI
        sinal_rsi_compra = rsi <= self.limite_rsi_inf
        sinal_rsi_venda = rsi >= self.limite_rsi_sup
        rsi_forca = 0
        if sinal_rsi_compra:
            # Quanto mais baixo o RSI, mais forte o sinal
            rsi_forca = (self.limite_rsi_inf - rsi) / self.limite_rsi_inf
            rsi_forca = max(0, min(1, rsi_forca))
        elif sinal_rsi_venda:
            rsi_forca = (rsi - self.limite_rsi_sup) / (100 - self.limite_rsi_sup)
            rsi_forca = max(0, min(1, rsi_forca))
        
        # Sinal MACD (cruzamento)
        if len(self.historico_macd) >= 2:
            macd_anterior, signal_anterior = self.historico_macd[-2][0], self.historico_macd[-2][1]
            cruzamento_alta = macd_line > macd_signal and macd_anterior <= signal_anterior
            cruzamento_baixa = macd_line < macd_signal and macd_anterior >= signal_anterior
        else:
            cruzamento_alta = macd_line > macd_signal
            cruzamento_baixa = macd_line < macd_signal
        
        sinal_macd_compra = cruzamento_alta or (macd_line > 0 and macd_line > macd_signal)
        sinal_macd_venda = cruzamento_baixa or (macd_line < 0 and macd_line < macd_signal)
        
        # Força do MACD (baseada no histograma)
        macd_forca = min(1, abs(histograma) / 10)  # Normaliza
        
        # Sinal Bollinger
        sinal_bb_compra = preco <= banda_inf if banda_inf else False
        sinal_bb_venda = preco >= banda_sup if banda_sup else False
        
        bb_forca = 0
        if sinal_bb_compra and banda_inf:
            # Distância da banda
            bb_forca = min(1, (banda_inf - preco) / banda_inf * 10)
        elif sinal_bb_venda and banda_sup:
            bb_forca = min(1, (preco - banda_sup) / banda_sup * 10)
        
        # Calcula pontuação ponderada
        pontuacao_compra = 0
        pontuacao_venda = 0
        
        if sinal_rsi_compra:
            pontuacao_compra += self.peso_rsi * (0.5 + rsi_forca * 0.5)
        if sinal_rsi_venda:
            pontuacao_venda += self.peso_rsi * (0.5 + rsi_forca * 0.5)
        
        if sinal_macd_compra:
            pontuacao_compra += self.peso_macd * (0.5 + macd_forca * 0.5)
        if sinal_macd_venda:
            pontuacao_venda += self.peso_macd * (0.5 + macd_forca * 0.5)
        
        if sinal_bb_compra:
            pontuacao_compra += self.peso_bb * (0.5 + bb_forca * 0.5)
        if sinal_bb_venda:
            pontuacao_venda += self.peso_bb * (0.5 + bb_forca * 0.5)
        
        # Contagem simples
        count_compra = sum([sinal_rsi_compra, sinal_macd_compra, sinal_bb_compra])
        count_venda = sum([sinal_rsi_venda, sinal_macd_venda, sinal_bb_venda])
        
        # Decisão final
        comprar = count_compra >= self.min_concordancia and pontuacao_compra > pontuacao_venda
        vender = count_venda >= self.min_concordancia and pontuacao_venda > pontuacao_compra
        
        detalhes = {
            'rsi': {'compra': sinal_rsi_compra, 'venda': sinal_rsi_venda, 'forca': rsi_forca, 'valor': rsi},
            'macd': {'compra': sinal_macd_compra, 'venda': sinal_macd_venda, 'forca': macd_forca, 
                     'line': macd_line, 'signal': macd_signal},
            'bb': {'compra': sinal_bb_compra, 'venda': sinal_bb_venda, 'forca': bb_forca,
                   'sup': banda_sup, 'inf': banda_inf},
            'count_compra': count_compra,
            'count_venda': count_venda,
            'pontuacao_compra': round(pontuacao_compra, 2),
            'pontuacao_venda': round(pontuacao_venda, 2)
        }
        
        return comprar, vender, detalhes
    
    # ============================================
    # PROCESSAMENTO PRINCIPAL
    # ============================================
    
    def processar_preco(self, preco, timestamp, volume=None, is_candle_closed=True, **kwargs):
        """
        Processa preço e combina sinais dos indicadores
        
        Args:
            preco: Preço atual
            timestamp: Timestamp
            volume: Volume (opcional)
            is_candle_closed: Se True, candle está fechado
        """
        self.ultimo_preco = preco
        self.historico_precos.append(preco)
        
        if volume is not None:
            self.volume_atual = volume
            self.historico_volumes.append(volume)
        
        # ============================================
        # COOLDOWN
        # ============================================
        if self.cooldown_periods_counter > 0:
            self.cooldown_periods_counter -= 1
            if self.cooldown_periods_counter == 0:
                self._log("COOLDOWN encerrado - Retomando operações", "INFO")
            return []
        
        # ============================================
        # DADOS SUFICIENTES?
        # ============================================
        min_precos = max(self.periodo_rsi + 5, 
                        self.macd_slow + self.macd_signal_period + 5, 
                        self.bb_periodo + 5)
        
        if len(self.historico_precos) < min_precos:
            return []
        
        # ============================================
        # CALCULA INDICADORES
        # ============================================
        rsi = self._calcular_rsi(self.historico_precos)
        macd_line, macd_signal_line, histograma = self._calcular_macd_corrigido(self.historico_precos)
        banda_sup, media_bb, banda_inf, largura_bb = self._calcular_bandas(self.historico_precos)
        
        # Registra MACD
        self.historico_macd.append((macd_line, macd_signal_line))
        self.historico_rsi.append(rsi)
        
        # ============================================
        # FILTRO DE TENDÊNCIA
        # ============================================
        tendencia, forca_tendencia = self._calcular_tendencia_ema200() if self.usar_filtro_tendencia else ('NEUTRO', 0)
        
        # ============================================
        # ANÁLISE DE SINAIS
        # ============================================
        comprar, vender, detalhes = self._analisar_sinais(
            preco, rsi, macd_line, macd_signal_line, histograma,
            banda_sup, media_bb, banda_inf
        )
        
        # ============================================
        # LOG PERIÓDICO
        # ============================================
        if len(self.historico_precos) % 20 == 0:
            print(f"  RSI: {rsi:.1f} | MACD: {macd_line:.4f} | Hist: {histograma:.4f}")
            print(f"  Sinais - Compra: {detalhes['count_compra']} ({detalhes['pontuacao_compra']:.2f}) | Venda: {detalhes['count_venda']} ({detalhes['pontuacao_venda']:.2f})")
            print(f"  Tendência: {tendencia} (força: {forca_tendencia:.1f}%)")
        
        ordens_executadas = []
        
        # ============================================
        # VERIFICA PROTECÇÕES
        # ============================================
        if self.em_posicao:
            trade_protecao = self._verificar_stop_take_trailing(
                preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
                self.trailing_stop_percent,
                rsi=round(rsi, 1), macd=round(macd_line, 4), histograma=round(histograma, 4))
            if trade_protecao:
                if trade_protecao['motivo'] == 'STOP_LOSS':
                    self.perdas_consecutivas += 1
                    self._log(f"Perdas consecutivas: {self.perdas_consecutivas}/{self.max_perdas_consecutivas}")
                    if self.perdas_consecutivas >= self.max_perdas_consecutivas:
                        self.cooldown_periods_counter = self.cooldown_max_periods
                        self._log(f"COOLDOWN ativado por {self.cooldown_max_periods} candles")
                        self.perdas_consecutivas = 0
                else:
                    self.perdas_consecutivas = 0
                ordens_executadas.append(trade_protecao)
                return ordens_executadas
        
        # ============================================
        # CONFIRMAÇÃO DE CANDLE
        # ============================================
        if self.usar_confirmacao_candle and not is_candle_closed:
            if comprar and not self.em_posicao:
                self.sinal_compra_pendente = True
                self.preco_sinal_compra = preco
                self._log(f"Sinal de COMPRA pendente - aguardando fechamento do candle", "SINAL")
            if vender and self.em_posicao:
                self.sinal_venda_pendente = True
                self.preco_sinal_venda = preco
                self._log(f"Sinal de VENDA pendente - aguardando fechamento do candle", "SINAL")
            return []
        
        # Reseta pendências
        sinal_compra_confirmado = self.sinal_compra_pendente
        sinal_venda_confirmado = self.sinal_venda_pendente
        self.sinal_compra_pendente = False
        self.sinal_venda_pendente = False
        
        # Usa sinal pendente ou atual
        comprar = comprar or sinal_compra_confirmado
        vender = vender or sinal_venda_confirmado
        
        # ============================================
        # SINAIS DE COMPRA
        # ============================================
        if comprar and not self.em_posicao:
            # Filtro de tendência: não comprar em tendência de baixa forte
            if self.usar_filtro_tendencia and tendencia == 'BAIXA' and forca_tendencia > 5:
                self._log(f"Tendência de baixa forte ({forca_tendencia:.1f}%), ignorando compra", "FILTRO")
            else:
                quantidade, valor = self._calcular_quantidade(preco)
                
                if quantidade and quantidade > 0:
                    trade = self.executar_compra(preco, quantidade, timestamp,
                                                rsi=round(rsi, 1),
                                                macd=round(macd_line, 4),
                                                histograma=round(histograma, 4),
                                                concordancia=detalhes['count_compra'],
                                                pontuacao=detalhes['pontuacao_compra'],
                                                tendencia=tendencia,
                                                banda_sup=round(banda_sup, 2) if banda_sup else None,
                                                media_bb=round(media_bb, 2) if media_bb else None,
                                                banda_inf=round(banda_inf, 2) if banda_inf else None)
                    
                    if trade:
                        self.em_posicao = True
                        self.preco_compra_medio = preco
                        self.quantidade_comprada_total = quantidade
                        self.maior_preco_posicao = preco
                        self.total_sinais_compra += 1
                        self.confianca_media_compra = (self.confianca_media_compra * (self.total_sinais_compra - 1) + 
                                                       detalhes['pontuacao_compra']) / self.total_sinais_compra
                        ordens_executadas.append(trade)
                        
                        self._log(f"COMPRA executada! Confiança: {detalhes['pontuacao_compra']:.2f} | {detalhes['count_compra']}/3 indicadores", "SINAL")
        
        # ============================================
        # SINAIS DE VENDA
        # ============================================
        elif vender and self.em_posicao:
            quantidade_vender = self.quantidade_comprada_total
            
            # Saída gradual baseada na força do sinal
            if self.usar_saida_gradual:
                if detalhes['count_venda'] >= 3 and detalhes['pontuacao_venda'] > 3:
                    quantidade_vender = self.quantidade_comprada_total  # Vende tudo
                elif detalhes['count_venda'] >= 2 and detalhes['pontuacao_venda'] > 2:
                    quantidade_vender = self.quantidade_comprada_total * 0.75  # Vende 75%
                elif detalhes['pontuacao_venda'] > 1.5:
                    quantidade_vender = self.quantidade_comprada_total * 0.5  # Vende 50%
                else:
                    quantidade_vender = self.quantidade_comprada_total * 0.25  # Vende 25%
                
                quantidade_vender = max(quantidade_vender, self.quantidade_comprada_total * 0.1)
            
            # Arredonda
            quantidade_vender = round(quantidade_vender, 8)
            
            if quantidade_vender > 0:
                trade = self.executar_venda(preco, quantidade_vender, timestamp,
                                           rsi=round(rsi, 1),
                                           macd=round(macd_line, 4),
                                           histograma=round(histograma, 4),
                                           concordancia=detalhes['count_venda'],
                                           pontuacao=detalhes['pontuacao_venda'],
                                           tendencia=tendencia,
                                           banda_sup=round(banda_sup, 2) if banda_sup else None,
                                           media_bb=round(media_bb, 2) if media_bb else None,
                                           banda_inf=round(banda_inf, 2) if banda_inf else None)
                
                if trade:
                    self.quantidade_comprada_total -= quantidade_vender
                    
                    if self.quantidade_comprada_total <= 0.00000001:
                        self.em_posicao = False
                        self.quantidade_comprada_total = 0
                        self.preco_compra_medio = 0
                        self.maior_preco_posicao = 0
                        self.total_sinais_venda += 1
                        self.confianca_media_venda = (self.confianca_media_venda * (self.total_sinais_venda - 1) + 
                                                      detalhes['pontuacao_venda']) / self.total_sinais_venda
                        self._log(f"VENDA TOTAL executada! Confiança: {detalhes['pontuacao_venda']:.2f}", "SINAL")
                    else:
                        self._log(f"VENDA PARCIAL executada! Vendido: {quantidade_vender:.8f}, Restam: {self.quantidade_comprada_total:.8f}", "SINAL")
                    
                    ordens_executadas.append(trade)
        
        return ordens_executadas
    
    def reset(self):
        """Reseta a estrategia"""
        super().reset()
        self.historico_macd = deque(maxlen=500)
        self.historico_rsi = deque(maxlen=500)
        self.historico_volumes = deque(maxlen=1000)
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self.perdas_consecutivas = 0
        self.cooldown_periods_counter = 0
        self.sinal_compra_pendente = False
        self.sinal_venda_pendente = False
        self.total_sinais_compra = 0
        self.total_sinais_venda = 0
        self.confianca_media_compra = 0
        self.confianca_media_venda = 0
        self._ema200 = 0
        self._ema200_pronta = False

    def get_configuracao(self):
        """Retorna a configuracao atual da estrategia"""
        if self.percentual_por_trade:
            gestao_quantidade = f"{self.percentual_por_trade*100}% do saldo"
        else:
            simbolo_asset = self.symbol.replace('USDT', '')
            gestao_quantidade = f"{self.quantidade_por_trade} {simbolo_asset} (fixo)"
        
        return {
            'nome': 'Combinação de Indicadores (RSI + MACD + Bollinger) - Versão Melhorada',
            'descricao': 'Opera quando pelo menos 2 indicadores concordam, com pesos diferentes, proteções completas, filtro de tendência e saída gradual.',
            'parametros': {
                'periodo_rsi': self.periodo_rsi,
                'sobrevenda_rsi': self.limite_rsi_inf,
                'sobrecompra_rsi': self.limite_rsi_sup,
                'macd_rapido': self.macd_fast,
                'macd_lento': self.macd_slow,
                'macd_sinal': self.macd_signal_period,
                'bb_periodo': self.bb_periodo,
                'bb_desvios': self.bb_desvios,
                'gestao_de_quantidade': gestao_quantidade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'peso_rsi': self.peso_rsi,
                'peso_macd': self.peso_macd,
                'peso_bb': self.peso_bb,
                'min_indicadores_concordando': self.min_concordancia,
                'filtro_tendencia_ema200': self.usar_filtro_tendencia,
                'confirmacao_candle': self.usar_confirmacao_candle,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%",
                'saida_gradual': self.usar_saida_gradual,
                'max_perdas_consecutivas': self.max_perdas_consecutivas,
                'cooldown_apos_perdas': self.cooldown_max_periods
            }
        }
    
    def get_relatorio_estendido(self):
        """Relatório estendido com estatísticas de sinais"""
        base = self.get_relatorio()
        
        base['indicadores'] = {
            'total_sinais_compra': self.total_sinais_compra,
            'total_sinais_venda': self.total_sinais_venda,
            'confianca_media_compra': round(self.confianca_media_compra, 2),
            'confianca_media_venda': round(self.confianca_media_venda, 2)
        }
        
        return base